BEGIN {
  FS = "/"
}
{ # Handle the presence or absence of leading slashes.
  if ($0 ~ /^\//) {
    path = "/";
  } else {
    path = "";
  }
  num_components = 0;
  for (i = 1; i <= NF; i++) {
    subdir = $i;
    # Skip empty path components; these come from before a leading slash or
    # from between repeated slashes.
    if (subdir != "") {
      num_components++;
      if (path ~ /[^\/]$/) {
        # The path already has contents and does not end with a slash, so we
        # need one as a separator.
        path = path "/";
      }
      path = path subdir;
      # SKIP is supplied by the caller.
      if (num_components > SKIP) {
        print path;
      }
    }
  }
}
