#!/usr/bin/env python3
"""HTML documentation generator converting Markdown files into styled HTML pages.

Converts Markdown documentation files into responsive HTML pages with top navigation,
print styles, interactive Mermaid diagrams, LaTeX math rendering, SVG/image diagram
embedding, GitHub-style callouts, and dark/light theme switching.
"""

import argparse
import dataclasses
import html
import os.path
import pathlib
import re
import shlex
import shutil
import sys
import textwrap
import tomllib
import typing

import markdown_it
import mdit_py_plugins.dollarmath
import mdit_py_plugins.tasklists

ALERT_TYPES: dict[str, tuple[str, str, str]] = {
    "NOTE": ("callout-note", "ℹ️", "Note"),
    "TIP": ("callout-tip", "💡", "Tip"),
    "IMPORTANT": ("callout-important", "📌", "Important"),
    "WARNING": ("callout-warning", "⚠️", "Warning"),
    "CAUTION": ("callout-caution", "🛑", "Caution"),
}


class PageDict(typing.TypedDict):
    """Schema for a single page entry in a TOML configuration file.

    Attributes:
        src: Source markdown file path relative to base directory.
        dest: Optional destination HTML file path relative to output directory.
        title: Optional full page title for the HTML head.
        short_title: Optional short title for navigation menus.
        diagrams: Optional list of diagram file paths to embed.
    """

    src: str
    dest: typing.NotRequired[str]
    title: typing.NotRequired[str]
    short_title: typing.NotRequired[str]
    diagrams: typing.NotRequired[list[str]]


class SiteConfigDict(typing.TypedDict, total=False):
    """Schema for the top-level site configuration in a TOML file.

    Attributes:
        site_title: Full site title for header and branding.
        title_suffix: Suffix for page titles in the HTML head.
        logo_icon: Icon or emoji for the navigation header.
        theme_key: LocalStorage key for persisting color theme.
        css_rel_path: Relative path to the CSS stylesheet.
        pages: List of page configuration dictionaries.
    """

    site_title: typing.NotRequired[str]
    title_suffix: typing.NotRequired[str]
    logo_icon: typing.NotRequired[str]
    theme_key: typing.NotRequired[str]
    css_rel_path: typing.NotRequired[str]
    pages: typing.NotRequired[list[PageDict]]


@dataclasses.dataclass(frozen=True)
class PageConfig:
    """Configuration for an individual documentation page.

    Attributes:
        src: Source markdown filename relative to base directory.
        dest: Destination HTML filename relative to output directory.
        title: Full page title for the HTML document head.
        short_title: Short title for navigation menu items.
        diagrams: List of diagram file paths to embed in this page.
    """

    src: str
    dest: str
    title: str
    short_title: str
    diagrams: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class SiteConfig:
    """Complete configuration for the documentation site.

    Attributes:
        site_title: Full site name displayed in the header.
        title_suffix: Suffix appended to individual page titles.
        logo_icon: Emoji or symbol icon for the header.
        theme_key: Key name used in localStorage for theme preference.
        css_rel_path: Relative URL/path to the CSS stylesheet.
        pages: List of configured pages to build.
    """

    site_title: str
    title_suffix: str
    logo_icon: str
    theme_key: str
    css_rel_path: str
    pages: list[PageConfig] = dataclasses.field(default_factory=list)


@typing.final
class Args(argparse.Namespace):
    """Typed container for parsed command line arguments.

    Attributes:
        dir: Base directory containing documentation files.
        config: Path to optional TOML configuration file.
        site_title: Site title for the header and document head.
        title_suffix: Title suffix for HTML page titles.
        logo_icon: Emoji or text icon for the site logo.
        theme_key: LocalStorage key for persisting theme selection.
        css_path: Relative path to stylesheet.
        output_dir: Destination directory for generated HTML files.
        inputs: List of specific markdown filenames to process.
    """

    dir: str
    config: str
    site_title: str
    title_suffix: str
    logo_icon: str
    theme_key: str
    css_path: str
    output_dir: str
    inputs: list[str]

    def __init__(
        self,
        dir: str = ".",
        config: str = "",
        site_title: str = "",
        title_suffix: str = "",
        logo_icon: str = "",
        theme_key: str = "",
        css_path: str = "",
        output_dir: str = "",
        inputs: list[str] | None = None,
    ) -> None:
        """Initializes the argument container with default values.

        Args:
            dir: Base directory containing documentation files.
            config: Path to optional TOML configuration file.
            site_title: Site title for the header and document head.
            title_suffix: Title suffix for HTML page titles.
            logo_icon: Emoji or text icon for the site logo.
            theme_key: LocalStorage key for persisting theme selection.
            css_path: Relative path to stylesheet.
            output_dir: Destination directory for generated HTML files.
            inputs: List of specific markdown filenames to process.
        """
        super().__init__()
        self.dir = dir
        self.config = config
        self.site_title = site_title
        self.title_suffix = title_suffix
        self.logo_icon = logo_icon
        self.theme_key = theme_key
        self.css_path = css_path
        self.output_dir = output_dir
        self.inputs = list(inputs) if inputs is not None else []


def create_argument_parser() -> argparse.ArgumentParser:
    """Creates and configures the command-line argument parser.

    Returns:
        Configured argparse.ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Convert Markdown documentation to styled, responsive HTML pages.",
    )
    _ = parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Base directory containing Markdown and asset files (default: current directory).",
    )
    _ = parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Path to TOML configuration file.",
    )
    _ = parser.add_argument(
        "--site-title",
        type=str,
        default="",
        help="Site title displayed in navigation header and page titles.",
    )
    _ = parser.add_argument(
        "--title-suffix",
        type=str,
        default="",
        help="Suffix appended to page titles (defaults to site title).",
    )
    _ = parser.add_argument(
        "--logo-icon",
        type=str,
        default="",
        help="Emoji or text icon for site header (default: 📄).",
    )
    _ = parser.add_argument(
        "--theme-key",
        type=str,
        default="",
        help="localStorage key for persisting dark/light mode preference.",
    )
    _ = parser.add_argument(
        "--css-path",
        type=str,
        default="",
        help="Relative path to CSS stylesheet (default: css/styles.css).",
    )
    _ = parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Destination directory for generated HTML files (defaults to base directory).",
    )
    _ = parser.add_argument(
        "inputs",
        nargs="*",
        type=str,
        default=None,
        help="Optional specific Markdown files to process.",
    )
    return parser


def create_markdown_parser() -> markdown_it.MarkdownIt:
    """Creates and configures a MarkdownIt parser with required extensions.

    Returns:
        A configured markdown_it.MarkdownIt parser instance.
    """
    md: markdown_it.MarkdownIt = markdown_it.MarkdownIt("commonmark")
    _ = md.enable("table")
    _ = md.enable("strikethrough")
    mdit_py_plugins.tasklists.tasklists_plugin(md)
    mdit_py_plugins.dollarmath.dollarmath_plugin(
        md,
        allow_space=False,
        allow_digits=False,
        double_inline=True,
    )
    return md


def render_markdown(md_parser: markdown_it.MarkdownIt, text: str) -> str:
    """Renders markdown text to HTML using the provided parser.

    Args:
        md_parser: Configured MarkdownIt parser instance.
        text: Raw markdown string.

    Returns:
        Rendered HTML string.
    """
    return typing.cast(str, md_parser.render(text))


def extract_title_from_markdown(content: str, default: str) -> str:
    """Extracts the first top-level heading (# Heading) from markdown text.

    Args:
        content: Raw markdown text content.
        default: Fallback title to return if no heading is found.

    Returns:
        Extracted heading title or default value.
    """
    match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return default


def post_process_html(html_content: str, current_page_dest: str = "") -> str:
    """Post-processes rendered HTML with tables, callouts, links, and mermaid diagrams.

    Args:
        html_content: Raw HTML rendered from Markdown.
        current_page_dest: Target HTML filename for reference during post-processing.

    Returns:
        Cleaned and enriched HTML string.
    """
    _ = current_page_dest
    processed: str = re.sub(
        r"(<table>.*?</table>)",
        r'<div class="table-wrapper">\1</div>',
        html_content,
        flags=re.DOTALL,
    )

    def replace_alert(match: re.Match[str]) -> str:
        """Converts a matched GitHub alert blockquote into a styled callout div.

        Args:
            match: Regex match containing alert type and alert body text.

        Returns:
            HTML string representing the styled callout box.
        """
        kind: str = match.group(1).upper()
        raw_body: str = match.group(2).strip()
        body: str
        if raw_body.startswith("</p>"):
            body = raw_body[4:].strip()
        elif raw_body.startswith("<p>"):
            body = raw_body
        else:
            body = f"<p>{raw_body}"
        css_class, icon, label = ALERT_TYPES.get(
            kind, ("callout-note", "ℹ️", kind.capitalize())
        )
        return (
            f'<div class="callout {css_class}">'
            + f'<div class="callout-header"><span class="callout-icon">{icon}</span> {label}</div>'
            + f'<div class="callout-body">{body}</div>'
            + "</div>"
        )

    alert_pattern: re.Pattern[str] = re.compile(
        r"<blockquote>\s*<p>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]"
        + r"\s*(?:<br\s*/?>)?\s*(.*?)\s*</blockquote>",
        re.DOTALL | re.IGNORECASE,
    )
    processed = alert_pattern.sub(replace_alert, processed)

    def replace_mermaid(match: re.Match[str]) -> str:
        """Converts mermaid code blocks into executable mermaid div containers.

        Args:
            match: Regex match containing escaped mermaid graph definition.

        Returns:
            HTML div tag containing unescaped mermaid graph syntax.
        """
        code: str = html.unescape(match.group(1))
        return f'<div class="mermaid">\n{code.strip()}\n</div>'

    processed = re.sub(
        r'<pre><code class="language-mermaid">([\s\S]*?)</code></pre>',
        replace_mermaid,
        processed,
    )

    def rewrite_link(match: re.Match[str]) -> str:
        """Rewrites markdown links (.md) to their target HTML filenames (.html).

        Args:
            match: Regex match containing target markdown link href and anchor.

        Returns:
            Rewritten href attribute string pointing to the HTML destination.
        """
        href: str = match.group(1)
        anchor: str = match.group(2) or ""
        if href.startswith(("http://", "https://", "//")):
            return match.group(0)
        target: str = href[:-3]
        return f'href="{target}.html{anchor}"'

    processed = re.sub(r'href="([^"#]+\.md)(#[^"]*)?"', rewrite_link, processed)

    return processed


def compute_relative_path(
    target_path: str,
    from_dir: pathlib.Path | None,
) -> str:
    """Computes a relative POSIX path from a directory to a target file or URL.

    Args:
        target_path: Destination path or URL.
        from_dir: Directory to compute the relative path from. If None, returns
            target_path unchanged.

    Returns:
        Relative POSIX path string or unchanged URL.
    """
    if from_dir is None or target_path.startswith(("http://", "https://", "//", "#")):
        return target_path
    rel = os.path.relpath(target_path, from_dir)
    return pathlib.Path(rel).as_posix()


def insert_diagrams(
    body_html: str,
    diagrams: list[str],
    current_page_dest: str = "",
) -> str:
    """Inserts diagram image cards after the primary page heading.

    Args:
        body_html: Rendered and post-processed HTML content of the page.
        diagrams: List of diagram file paths to embed.
        current_page_dest: Optional destination path of the current page for relative links.

    Returns:
        HTML string with diagram cards inserted after </h1> or at the beginning.
    """
    if not diagrams:
        return body_html

    current_dir = pathlib.Path(current_page_dest).parent if current_page_dest else None
    diagram_html = ""
    for diag in diagrams:
        diag_file = pathlib.Path(diag).name
        diag_src = compute_relative_path(diag, current_dir)
        diagram_html += textwrap.dedent(f"""
            <div class="diagram-card">
              <img src="{diag_src}" alt="{diag_file}" loading="lazy" />
              <div class="diagram-caption">Architectural Drawing: {diag_file}</div>
            </div>
            """)
    parts = body_html.split("</h1>", 1)
    if len(parts) == 2:
        return parts[0] + "</h1>" + diagram_html + parts[1]
    return diagram_html + body_html


def build_header(
    pages: list[PageConfig],
    current_dest: str,
    site_title: str,
    logo_icon: str,
) -> str:
    """Builds the top navigation header bar HTML.

    Args:
        pages: List of configured pages in the site.
        current_dest: Destination filename of the current page being built.
        site_title: Title of the site displayed in the header.
        logo_icon: Emoji or symbol icon displayed beside site title.

    Returns:
        HTML string of the header navigation element.
    """
    current_dir = (
        pathlib.Path(current_dest).parent if current_dest else pathlib.Path(".")
    )
    nav_items: list[str] = []
    for page in pages:
        active_class: str = " active" if page.dest == current_dest else ""
        rel_dest = compute_relative_path(page.dest, current_dir)
        nav_items.append(
            f'<a href="{rel_dest}" class="nav-item{active_class}">{page.short_title}</a>'
        )

    nav_html: str = "\n".join(nav_items)
    home_link: str = compute_relative_path(pages[0].dest, current_dir) if pages else "#"
    template = textwrap.dedent("""
        <header class="site-header">
          <div class="header-container">
            <a href="{home_link}" class="logo-area">
              <span class="logo-icon">{logo_icon}</span>
              <span>{site_title}</span>
            </a>
            <nav class="nav-links">
              {nav_html}
            </nav>
            <div class="header-actions">
              <button class="btn-action" onclick="toggleTheme()" title="Toggle Dark/Light Mode">🌓 Mode</button>
              <button class="btn-action btn-action-primary" onclick="window.print()" title="Print Current Document">🖨️ Print</button>
            </div>
          </div>
        </header>
        """)
    return template.format(
        home_link=home_link,
        logo_icon=logo_icon,
        site_title=site_title,
        nav_html=nav_html,
    )


def build_theme_script(theme_key: str) -> str:
    """Builds JavaScript for dark/light mode toggle with localStorage persistence.

    Args:
        theme_key: Key name used in localStorage for storing user theme preference.

    Returns:
        HTML script tag string containing the theme management functions.
    """
    return textwrap.dedent(f"""
        <script>
          function initTheme() {{
            const saved = localStorage.getItem('{theme_key}');
            if (saved) {{
              document.documentElement.setAttribute('data-theme', saved);
            }} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
              document.documentElement.setAttribute('data-theme', 'dark');
            }}
          }}
          function toggleTheme() {{
            const current = document.documentElement.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', target);
            localStorage.setItem('{theme_key}', target);
            location.reload();
          }}
          initTheme();
        </script>
        """)


def build_regeneration_command(
    argv: list[str] | None = None,
    program_name: str | None = None,
) -> str:
    """Builds the command string used to regenerate HTML pages.

    Args:
        argv: Optional list of command line arguments used for invocation.
            If None, attempts to extract non-test arguments from sys.argv.
        program_name: Optional name of the script. Defaults to the basename of this script.

    Returns:
        A shell-quoted command string.
    """
    if program_name is None:
        if sys.argv and sys.argv[0]:
            name = sys.argv[0]
            if (
                name.startswith("./")
                and pathlib.Path(name).name == pathlib.Path(__file__).name
            ):
                program_name = name
            else:
                program_name = pathlib.Path(__file__).name
        else:
            program_name = pathlib.Path(__file__).name

    if argv is not None:
        args_list = argv
    else:
        script_path = pathlib.Path(sys.argv[0]) if sys.argv else None
        if script_path and script_path.name == pathlib.Path(__file__).name:
            args_list = sys.argv[1:]
        else:
            args_list = []

    if args_list:
        return shlex.join([program_name, *args_list])
    return program_name


def render_page(
    page: PageConfig,
    body_html: str,
    site_config: SiteConfig,
    regen_command: str = "markdown_to_html.py",
) -> str:
    """Wraps body content in full HTML document template with head and scripts.

    Args:
        page: Page configuration for the current document.
        body_html: Post-processed body HTML content.
        site_config: Site-wide configuration parameters.
        regen_command: Shell command string used to regenerate this HTML document.

    Returns:
        Complete HTML document string.
    """
    header_html = build_header(
        pages=site_config.pages,
        current_dest=page.dest,
        site_title=site_config.site_title,
        logo_icon=site_config.logo_icon,
    )
    theme_script = build_theme_script(site_config.theme_key)
    current_dir = pathlib.Path(page.dest).parent
    css_path = compute_relative_path(site_config.css_rel_path, current_dir)

    template = textwrap.dedent("""\
        <!--
          Generated by markdown_to_html.py. Do not edit directly.
          Regenerate with: {regen_command}
        -->
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>{title} — {title_suffix}</title>
          <link rel="stylesheet" href="{css_path}">
          <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
          <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
          <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
          <script>
            document.addEventListener("DOMContentLoaded", function() {{
              const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
              mermaid.initialize({{
                startOnLoad: true,
                theme: isDark ? 'dark' : 'neutral',
                flowchart: {{ useMaxWidth: true, htmlLabels: true }},
                securityLevel: 'loose',
                logLevel: 'warn'
              }});
              if (typeof katex !== 'undefined') {{
                document.querySelectorAll('.math.inline').forEach(function(el) {{
                  katex.render(el.textContent, el, {{ throwOnError: false, displayMode: false }});
                }});
                document.querySelectorAll('.math.block').forEach(function(el) {{
                  katex.render(el.textContent, el, {{ throwOnError: false, displayMode: true }});
                }});
              }}
            }});
          </script>
        </head>
        <body>
          {header_html}
          <main class="page-container">
            {body_html}
          </main>
          {theme_script}
        </body>
        </html>
        """)
    return template.format(
        regen_command=regen_command,
        title=page.title,
        title_suffix=site_config.title_suffix,
        css_path=css_path,
        header_html=header_html,
        body_html=body_html,
        theme_script=theme_script,
    )


def discover_pages(
    base_dir: pathlib.Path,
    input_files: list[str] | None = None,
) -> list[PageConfig]:
    """Auto-discovers markdown files in the directory and generates PageConfigs.

    Args:
        base_dir: Directory containing Markdown documentation.
        input_files: Optional list of explicit markdown files to include.

    Returns:
        List of discovered PageConfig instances.
    """
    filenames: list[str]
    if input_files:
        filenames = list(input_files)
    else:
        md_paths = sorted(
            p
            for p in base_dir.glob("*.md")
            if p.is_file() and p.name != "GEMINI.md" and not p.name.startswith(".")
        )
        filenames = [p.name for p in md_paths]

    if not filenames:
        return []

    ordered_filenames: list[str] = list(filenames)
    if not input_files and "README.md" in ordered_filenames:
        ordered_filenames.remove("README.md")
        ordered_filenames.insert(0, "README.md")

    pages: list[PageConfig] = []
    for filename in ordered_filenames:
        file_path = base_dir / filename
        content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        stem = pathlib.Path(filename).stem
        title = extract_title_from_markdown(content, default=stem)
        short_title = title.split("—")[-1].strip() if "—" in title else title
        if len(short_title) > 20:
            short_title = stem
        dest = pathlib.Path(filename).with_suffix(".html").as_posix()
        pages.append(
            PageConfig(
                src=filename,
                dest=dest,
                title=title,
                short_title=short_title,
            )
        )

    return pages


def load_config_file(filepath: pathlib.Path) -> SiteConfigDict:
    """Loads and returns site configuration from a TOML file.

    Args:
        filepath: Path to the TOML configuration file.

    Returns:
        A SiteConfigDict containing the parsed configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        tomllib.TOMLDecodeError: If the configuration file contains invalid TOML.
    """
    with filepath.open("rb") as f:
        raw_data = tomllib.load(f)
    config: SiteConfigDict = typing.cast(SiteConfigDict, typing.cast(object, raw_data))
    return config


def resolve_site_config(
    args: Args,
    base_dir: pathlib.Path,
) -> SiteConfig:
    """Resolves and merges site configuration from CLI arguments and TOML file.

    Args:
        args: Parsed command-line arguments.
        base_dir: Resolved base directory containing files.

    Returns:
        A fully initialized SiteConfig instance.
    """
    config_dict: SiteConfigDict = {}
    config_path: pathlib.Path | None = None

    if args.config:
        config_path = pathlib.Path(args.config)
        if not config_path.is_absolute():
            config_path = (base_dir / config_path).resolve()
    else:
        candidate = base_dir / "markdown-to-html.toml"
        if candidate.is_file():
            config_path = candidate
        else:
            candidate_site = base_dir / "site.toml"
            if candidate_site.is_file():
                config_path = candidate_site

    if config_path and config_path.is_file():
        config_dict = load_config_file(config_path)

    site_title = (
        args.site_title
        or config_dict.get("site_title")
        or base_dir.name.replace("-", " ").replace("_", " ").title()
        or "Documentation"
    )

    title_suffix = args.title_suffix or config_dict.get("title_suffix") or site_title

    logo_icon = args.logo_icon or config_dict.get("logo_icon") or "📄"

    default_theme_key = (
        re.sub(r"[^a-zA-Z0-9]+", "-", site_title.lower()).strip("-") + "-theme"
    )
    theme_key = (
        args.theme_key
        or config_dict.get("theme_key")
        or (default_theme_key if default_theme_key != "-theme" else "site-theme")
    )

    css_rel_path = args.css_path or config_dict.get("css_rel_path") or "css/styles.css"

    pages: list[PageConfig] = []
    toml_pages = config_dict.get("pages")
    if toml_pages and not args.inputs:
        for p in toml_pages:
            src = p["src"]
            dest = p.get("dest") or pathlib.Path(src).with_suffix(".html").as_posix()
            file_path = base_dir / src
            file_content = (
                file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            )
            title = p.get("title") or extract_title_from_markdown(
                file_content, default=pathlib.Path(src).stem
            )
            short_title = p.get("short_title") or title
            diagrams = list(p.get("diagrams", []))
            pages.append(
                PageConfig(
                    src=src,
                    dest=dest,
                    title=title,
                    short_title=short_title,
                    diagrams=diagrams,
                )
            )
    else:
        pages = discover_pages(base_dir, args.inputs if args.inputs else None)

    return SiteConfig(
        site_title=site_title,
        title_suffix=title_suffix,
        logo_icon=logo_icon,
        theme_key=theme_key,
        css_rel_path=css_rel_path,
        pages=pages,
    )


def copy_stylesheet_if_needed(
    output_dir: pathlib.Path,
    css_rel_path: str,
    program_dir: pathlib.Path | None = None,
) -> bool:
    """Copies default stylesheet from program directory to output directory if missing.

    Args:
        output_dir: Destination directory where HTML files and assets are generated.
        css_rel_path: Relative path to the CSS stylesheet (e.g. 'css/styles.css').
        program_dir: Directory containing the program and default assets. If None,
            uses the directory of this script.

    Returns:
        True if the stylesheet was copied, False otherwise.
    """
    if css_rel_path.startswith(("http://", "https://", "//")):
        return False

    dest_css_path = output_dir / css_rel_path
    if dest_css_path.exists():
        return False

    source_base = (
        program_dir
        if program_dir is not None
        else pathlib.Path(__file__).resolve().parent
    )
    source_css_path = source_base / css_rel_path
    if not source_css_path.is_file():
        print(f"Warning: Stylesheet {source_css_path} not found to copy.")
        return False

    dest_css_path.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.copy2(source_css_path, dest_css_path)
    print(f"  ✓ Copied stylesheet to: {dest_css_path}")
    return True


def generate_individual_pages(
    site_config: SiteConfig,
    base_dir: pathlib.Path,
    output_dir: pathlib.Path,
    md_parser: markdown_it.MarkdownIt,
    program_dir: pathlib.Path | None = None,
    regen_command: str | None = None,
) -> list[pathlib.Path]:
    """Generates standalone HTML files for each configured Markdown document.

    Args:
        site_config: Site configuration containing pages and styling options.
        base_dir: Directory containing input source markdown and diagrams.
        output_dir: Directory where destination HTML files will be written.
        md_parser: Configured MarkdownIt parser instance.
        program_dir: Directory containing program executable and default assets.
        regen_command: Optional regeneration command string for the HTML comment.

    Returns:
        List of paths to the successfully generated HTML files.
    """
    effective_regen_command = (
        regen_command if regen_command is not None else build_regeneration_command()
    )
    print(f"Generating HTML pages in {output_dir}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    _ = copy_stylesheet_if_needed(
        output_dir=output_dir,
        css_rel_path=site_config.css_rel_path,
        program_dir=program_dir,
    )
    generated_files: list[pathlib.Path] = []

    for page in site_config.pages:
        src_path: pathlib.Path = base_dir / page.src
        dest_path: pathlib.Path = output_dir / page.dest

        if not src_path.exists():
            print(f"Warning: {src_path} does not exist, skipping.")
            continue

        raw_md: str = src_path.read_text(encoding="utf-8")
        parsed_html: str = render_markdown(md_parser, raw_md)
        processed_html: str = post_process_html(parsed_html, page.dest)
        body_with_diagrams: str = insert_diagrams(
            processed_html, page.diagrams, page.dest
        )
        full_html: str = render_page(
            page,
            body_with_diagrams,
            site_config,
            regen_command=effective_regen_command,
        )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        _ = dest_path.write_text(full_html, encoding="utf-8")
        generated_files.append(dest_path)
        print(f"  ✓ Written: {page.dest}")

    return generated_files


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint for generating documentation.

    Args:
        argv: Optional command line argument list. If None, uses sys.argv[1:].

    Returns:
        Exit status code (0 for success).
    """
    parser = create_argument_parser()
    args = parser.parse_args(args=argv, namespace=Args())

    base_dir = pathlib.Path(args.dir).resolve()
    output_dir = (
        pathlib.Path(args.output_dir).resolve() if args.output_dir else base_dir
    )

    site_config = resolve_site_config(args, base_dir)
    md_parser = create_markdown_parser()

    regen_command = build_regeneration_command(argv)
    _ = generate_individual_pages(
        site_config,
        base_dir,
        output_dir,
        md_parser,
        regen_command=regen_command,
    )
    print("\nAll HTML documents generated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
