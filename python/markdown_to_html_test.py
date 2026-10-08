#!/usr/bin/env python3
"""Unit tests for markdown_to_html.py."""

import pathlib
import tempfile
import textwrap
import typing
import unittest
from unittest import mock

import markdown_to_html


class TestMarkdownToHtml(unittest.TestCase):
    """Test suite for Markdown to HTML converter."""

    def test_create_markdown_parser(self) -> None:
        """Tests that the markdown parser is configured with required extensions."""
        parser = markdown_to_html.create_markdown_parser()
        rendered: str = markdown_to_html.render_markdown(
            parser,
            "# Hello World\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n~~strike~~",
        )
        self.assertIn("<h1>Hello World</h1>", rendered)
        self.assertIn("<table>", rendered)
        self.assertIn("<s>strike</s>", rendered)

    def test_render_markdown(self) -> None:
        """Tests standard markdown string rendering."""
        parser = markdown_to_html.create_markdown_parser()
        result = markdown_to_html.render_markdown(parser, "**Bold Text**")
        self.assertIn("<strong>Bold Text</strong>", result)

    def test_extract_title_from_markdown(self) -> None:
        """Tests heading extraction from markdown text."""
        content = "<!-- comment -->\n\n# Document Title\n\nBody text."
        title = markdown_to_html.extract_title_from_markdown(
            content, default="Fallback"
        )
        self.assertEqual(title, "Document Title")

        no_header = "Just paragraph content without h1."
        fallback = markdown_to_html.extract_title_from_markdown(
            no_header, default="Fallback"
        )
        self.assertEqual(fallback, "Fallback")

    def test_post_process_html_table_wrapping(self) -> None:
        """Tests that HTML tables are wrapped in a responsive wrapper."""
        raw_html = "<p>Intro</p><table><tr><td>Data</td></tr></table><p>Outro</p>"
        processed = markdown_to_html.post_process_html(raw_html)
        self.assertIn(
            '<div class="table-wrapper"><table><tr><td>Data</td></tr></table></div>',
            processed,
        )

    def test_post_process_html_alerts(self) -> None:
        """Tests that GitHub-style alert blockquotes are converted to callouts."""
        raw_note = textwrap.dedent("""
            <blockquote>
            <p>[!NOTE]<br />
            This is an important note.</p>
            </blockquote>
            """).strip()
        processed_note = markdown_to_html.post_process_html(raw_note)
        self.assertIn('<div class="callout callout-note">', processed_note)
        self.assertIn("Note", processed_note)
        self.assertIn("This is an important note.", processed_note)

        raw_tip = "<blockquote><p>[!TIP] Helpful tip text.</p></blockquote>"
        processed_tip = markdown_to_html.post_process_html(raw_tip)
        self.assertIn('<div class="callout callout-tip">', processed_tip)
        self.assertIn("Tip", processed_tip)
        self.assertIn("Helpful tip text.", processed_tip)

        raw_multiline = textwrap.dedent("""
            <blockquote>
            <p>[!IMPORTANT]
            <strong>Important Header</strong></p>
            <ol><li>Step 1</li></ol>
            </blockquote>
            """).strip()
        processed_multiline = markdown_to_html.post_process_html(raw_multiline)
        self.assertIn('<div class="callout callout-important">', processed_multiline)
        self.assertIn("<p><strong>Important Header</strong></p>", processed_multiline)
        self.assertIn("<ol><li>Step 1</li></ol>", processed_multiline)

        raw_warning = textwrap.dedent("""
            <blockquote>
            <p>[!WARNING]</p>
            <p>Warning message.</p>
            </blockquote>
            """).strip()
        processed_warning = markdown_to_html.post_process_html(raw_warning)
        self.assertIn('<div class="callout callout-warning">', processed_warning)
        self.assertIn("<p>Warning message.</p>", processed_warning)

        raw_caution = "<blockquote><p>[!CAUTION] Danger ahead.</p></blockquote>"
        processed_caution = markdown_to_html.post_process_html(raw_caution)
        self.assertIn('<div class="callout callout-caution">', processed_caution)
        self.assertIn("Caution", processed_caution)

    def test_post_process_html_mermaid(self) -> None:
        """Tests that mermaid code blocks are converted to mermaid div containers."""
        raw_html = (
            '<pre><code class="language-mermaid">flowchart TD\n'
            "A --&gt; B\n"
            "</code></pre>"
        )
        processed = markdown_to_html.post_process_html(raw_html)
        self.assertIn('<div class="mermaid">\nflowchart TD\nA --> B\n</div>', processed)

    def test_post_process_html_link_rewriting(self) -> None:
        """Tests that markdown links are rewritten to HTML destinations."""
        raw_html = (
            '<a href="guide.md">Guide</a> and '
            '<a href="README.md#summary">Home</a> and '
            '<a href="https://example.com/other.md">External</a>'
        )
        processed = markdown_to_html.post_process_html(raw_html)
        self.assertIn('href="guide.html"', processed)
        self.assertIn('href="index.html#summary"', processed)
        self.assertIn('href="https://example.com/other.md"', processed)

    def test_insert_diagrams(self) -> None:
        """Tests embedding diagram cards after the first heading."""
        body = "<h1>Title</h1><p>Content</p>"
        diagrams = ["diagrams/elevation.svg"]
        result = markdown_to_html.insert_diagrams(body, diagrams)
        self.assertIn('<div class="diagram-card">', result)
        self.assertIn('src="diagrams/elevation.svg"', result)
        self.assertIn("Architectural Drawing: elevation.svg", result)

        # When no </h1> tag is present
        body_no_h1 = "<p>No heading</p>"
        result_no_h1 = markdown_to_html.insert_diagrams(body_no_h1, diagrams)
        self.assertTrue(result_no_h1.startswith('\n<div class="diagram-card">'))

        # When diagrams list is empty
        result_empty = markdown_to_html.insert_diagrams(body, [])
        self.assertEqual(result_empty, body)

    def test_build_header(self) -> None:
        """Tests header HTML rendering including active page marking."""
        pages = [
            markdown_to_html.PageConfig(
                src="README.md",
                dest="index.html",
                title="Home",
                short_title="Overview",
            ),
            markdown_to_html.PageConfig(
                src="specs.md",
                dest="specs.html",
                title="Specs",
                short_title="Specifications",
            ),
        ]
        header = markdown_to_html.build_header(
            pages=pages,
            current_dest="index.html",
            site_title="Test Project",
            logo_icon="🛠️",
        )
        self.assertIn("Test Project", header)
        self.assertIn("🛠️", header)
        self.assertIn('href="index.html" class="nav-item active"', header)
        self.assertIn('href="specs.html" class="nav-item"', header)
        self.assertIn("toggleTheme()", header)
        self.assertIn("window.print()", header)

    def test_build_theme_script(self) -> None:
        """Tests theme script generation with specified storage key."""
        script = markdown_to_html.build_theme_script("custom-theme")
        self.assertIn("custom-theme", script)
        self.assertIn("location.reload()", script)
        self.assertIn("data-theme", script)

    def test_render_page(self) -> None:
        """Tests rendering of complete HTML document with template."""
        page = markdown_to_html.PageConfig(
            src="index.md",
            dest="index.html",
            title="Home",
            short_title="Home",
        )
        site_config = markdown_to_html.SiteConfig(
            site_title="Project Alpha",
            title_suffix="Alpha",
            logo_icon="🚀",
            theme_key="alpha-theme",
            css_rel_path="css/styles.css",
            pages=[page],
        )
        html_out = markdown_to_html.render_page(
            page=page,
            body_html="<p>Hello World</p>",
            site_config=site_config,
        )
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("<title>Home — Alpha</title>", html_out)
        self.assertIn('<link rel="stylesheet" href="css/styles.css">', html_out)
        self.assertIn("mermaid.initialize", html_out)
        self.assertIn("<p>Hello World</p>", html_out)

    def test_load_config_file(self) -> None:
        """Tests parsing a TOML configuration file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = pathlib.Path(tmp_dir) / "markdown-to-html.toml"
            _ = config_file.write_text(
                textwrap.dedent("""
                    site_title = "Test Site"
                    logo_icon = "⭐"
                    [[pages]]
                    src = "doc.md"
                    dest = "doc.html"
                    title = "Document"
                    """),
                encoding="utf-8",
            )
            parsed = markdown_to_html.load_config_file(config_file)
            self.assertEqual(parsed.get("site_title"), "Test Site")
            self.assertEqual(parsed.get("logo_icon"), "⭐")
            pages = parsed.get("pages")
            self.assertIsNotNone(pages)
            if pages:
                self.assertEqual(len(pages), 1)
                self.assertEqual(pages[0]["src"], "doc.md")

    def test_discover_pages_single_document(self) -> None:
        """Tests page auto-discovery when directory contains only one markdown file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            guide = base_dir / "guide.md"
            _ = guide.write_text("# Complete Guide\n\nContent.", encoding="utf-8")

            pages = markdown_to_html.discover_pages(base_dir)
            self.assertEqual(len(pages), 2)
            self.assertEqual(pages[0].dest, "index.html")
            self.assertEqual(pages[0].title, "Complete Guide")
            self.assertEqual(pages[1].dest, "guide.html")
            self.assertEqual(pages[1].title, "Complete Guide")

    def test_discover_pages_multiple_documents(self) -> None:
        """Tests page auto-discovery with README.md and multiple markdown files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            _ = (base_dir / "README.md").write_text(
                "# Main Overview\n", encoding="utf-8"
            )
            _ = (base_dir / "01_specs.md").write_text(
                "# 01 — Specifications\n", encoding="utf-8"
            )
            _ = (base_dir / "02_notes.md").write_text("# Notes\n", encoding="utf-8")
            # GEMINI.md should be ignored in auto-discovery
            _ = (base_dir / "GEMINI.md").write_text(
                "# Internal Instructions\n", encoding="utf-8"
            )

            pages = markdown_to_html.discover_pages(base_dir)
            dests = [p.dest for p in pages]
            self.assertEqual(dests, ["index.html", "01_specs.html", "02_notes.html"])
            self.assertEqual(pages[0].title, "Main Overview")
            self.assertEqual(pages[1].title, "01 — Specifications")

    def test_resolve_site_config(self) -> None:
        """Tests resolving site configuration from CLI arguments and defaults."""
        args = markdown_to_html.Args(
            dir=".",
            site_title="Custom Title",
            logo_icon="💎",
            theme_key="custom-key",
            css_path="custom.css",
        )
        base_dir = pathlib.Path(".")
        config = markdown_to_html.resolve_site_config(args, base_dir)
        self.assertEqual(config.site_title, "Custom Title")
        self.assertEqual(config.logo_icon, "💎")
        self.assertEqual(config.theme_key, "custom-key")
        self.assertEqual(config.css_rel_path, "custom.css")

    def test_generate_individual_pages(self) -> None:
        """Tests generating actual HTML files on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            md_file = base_dir / "test.md"
            _ = md_file.write_text("# Test Page\n\nSome text.", encoding="utf-8")

            page = markdown_to_html.PageConfig(
                src="test.md",
                dest="test.html",
                title="Test Page",
                short_title="Test",
            )
            site_config = markdown_to_html.SiteConfig(
                site_title="Test Site",
                title_suffix="Test",
                logo_icon="📄",
                theme_key="test-theme",
                css_rel_path="css/styles.css",
                pages=[page],
            )
            parser = markdown_to_html.create_markdown_parser()
            written = markdown_to_html.generate_individual_pages(
                site_config=site_config,
                base_dir=base_dir,
                output_dir=base_dir,
                md_parser=parser,
            )
            self.assertEqual(len(written), 1)
            dest = base_dir / "test.html"
            self.assertTrue(dest.exists())
            html_content = dest.read_text(encoding="utf-8")
            self.assertIn("<h1>Test Page</h1>", html_content)

    def test_main(self) -> None:
        """Tests main CLI orchestration function."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            _ = (base_dir / "README.md").write_text("# Readme\n", encoding="utf-8")
            exit_code = markdown_to_html.main(["--dir", str(base_dir)])
            self.assertEqual(exit_code, 0)
            self.assertTrue((base_dir / "index.html").exists())

    def test_main_with_mock(self) -> None:
        """Tests that main orchestrates argument parsing and generation."""
        mock_generate = typing.cast(
            mock.Mock,
            mock.create_autospec(
                markdown_to_html.generate_individual_pages, return_value=[]
            ),
        )
        with mock.patch.object(
            markdown_to_html, "generate_individual_pages", mock_generate
        ):
            exit_code = markdown_to_html.main(["--dir", "."])
            self.assertEqual(exit_code, 0)
            mock_generate.assert_called_once()

    def test_discover_pages_empty(self) -> None:
        """Tests page auto-discovery in an empty directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pages = markdown_to_html.discover_pages(pathlib.Path(tmp_dir))
            self.assertEqual(pages, [])

    def test_discover_pages_long_title(self) -> None:
        """Tests page auto-discovery with a long heading title."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            doc = base_dir / "long_doc.md"
            _ = doc.write_text(
                "# This Is A Very Long Document Title That Exceeds Twenty Characters\n",
                encoding="utf-8",
            )
            # Add README to trigger multi-file branch
            _ = (base_dir / "README.md").write_text("# Home\n", encoding="utf-8")
            pages = markdown_to_html.discover_pages(base_dir)
            self.assertEqual(len(pages), 2)
            self.assertEqual(pages[1].short_title, "long_doc")

    def test_resolve_site_config_with_config_file(self) -> None:
        """Tests resolving site configuration from an explicit config file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            config_file = base_dir / "custom.toml"
            _ = config_file.write_text(
                textwrap.dedent("""
                    site_title = "Config Title"
                    title_suffix = "Suffix"
                    logo_icon = "🌟"
                    theme_key = "my-theme"
                    css_rel_path = "assets/style.css"
                    [[pages]]
                    src = "doc.md"
                    dest = "doc.html"
                    title = "Custom Page"
                    short_title = "CP"
                    diagrams = ["diagram.svg"]
                    """),
                encoding="utf-8",
            )
            args = markdown_to_html.Args(dir=str(base_dir), config=str(config_file))
            site_config = markdown_to_html.resolve_site_config(args, base_dir)
            self.assertEqual(site_config.site_title, "Config Title")
            self.assertEqual(site_config.title_suffix, "Suffix")
            self.assertEqual(site_config.logo_icon, "🌟")
            self.assertEqual(site_config.theme_key, "my-theme")
            self.assertEqual(site_config.css_rel_path, "assets/style.css")
            self.assertEqual(len(site_config.pages), 1)
            self.assertEqual(site_config.pages[0].diagrams, ["diagram.svg"])

    def test_resolve_site_config_with_site_toml(self) -> None:
        """Tests resolving site configuration when site.toml is present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            site_toml = base_dir / "site.toml"
            _ = site_toml.write_text(
                'site_title = "Site TOML Title"\n',
                encoding="utf-8",
            )
            args = markdown_to_html.Args(dir=str(base_dir))
            site_config = markdown_to_html.resolve_site_config(args, base_dir)
            self.assertEqual(site_config.site_title, "Site TOML Title")

    def test_generate_individual_pages_missing_file(self) -> None:
        """Tests that nonexistent source files are skipped gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = pathlib.Path(tmp_dir)
            page = markdown_to_html.PageConfig(
                src="missing.md",
                dest="missing.html",
                title="Missing",
                short_title="Missing",
            )
            site_config = markdown_to_html.SiteConfig(
                site_title="Test",
                title_suffix="Test",
                logo_icon="📄",
                theme_key="test-theme",
                css_rel_path="css/styles.css",
                pages=[page],
            )
            parser = markdown_to_html.create_markdown_parser()
            written = markdown_to_html.generate_individual_pages(
                site_config=site_config,
                base_dir=base_dir,
                output_dir=base_dir,
                md_parser=parser,
            )
            self.assertEqual(written, [])

    def test_copy_stylesheet_if_needed_when_already_exists(self) -> None:
        """Tests that stylesheet is not overwritten if it already exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = pathlib.Path(tmp_dir)
            existing_css = output_dir / "css/styles.css"
            existing_css.parent.mkdir(parents=True, exist_ok=True)
            _ = existing_css.write_text("/* existing */", encoding="utf-8")

            copied = markdown_to_html.copy_stylesheet_if_needed(
                output_dir=output_dir,
                css_rel_path="css/styles.css",
            )
            self.assertFalse(copied)
            self.assertEqual(existing_css.read_text(encoding="utf-8"), "/* existing */")

    def test_copy_stylesheet_if_needed_copies_when_missing(self) -> None:
        """Tests that stylesheet is copied from program directory when missing."""
        with (
            tempfile.TemporaryDirectory() as tmp_out,
            tempfile.TemporaryDirectory() as tmp_prog,
        ):
            output_dir = pathlib.Path(tmp_out)
            program_dir = pathlib.Path(tmp_prog)
            source_css = program_dir / "css/styles.css"
            source_css.parent.mkdir(parents=True, exist_ok=True)
            _ = source_css.write_text("/* default styles */", encoding="utf-8")

            copied = markdown_to_html.copy_stylesheet_if_needed(
                output_dir=output_dir,
                css_rel_path="css/styles.css",
                program_dir=program_dir,
            )
            self.assertTrue(copied)
            dest_css = output_dir / "css/styles.css"
            self.assertTrue(dest_css.exists())
            self.assertEqual(
                dest_css.read_text(encoding="utf-8"), "/* default styles */"
            )

    def test_copy_stylesheet_if_needed_remote_url(self) -> None:
        """Tests that remote stylesheet URLs are skipped."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            copied = markdown_to_html.copy_stylesheet_if_needed(
                output_dir=pathlib.Path(tmp_dir),
                css_rel_path="https://cdn.example.com/styles.css",
            )
            self.assertFalse(copied)

    def test_copy_stylesheet_if_needed_source_missing(self) -> None:
        """Tests handling when stylesheet source does not exist in program directory."""
        with (
            tempfile.TemporaryDirectory() as tmp_out,
            tempfile.TemporaryDirectory() as tmp_prog,
        ):
            copied = markdown_to_html.copy_stylesheet_if_needed(
                output_dir=pathlib.Path(tmp_out),
                css_rel_path="css/missing.css",
                program_dir=pathlib.Path(tmp_prog),
            )
            self.assertFalse(copied)


if __name__ == "__main__":
    _ = unittest.main()
