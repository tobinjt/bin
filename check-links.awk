# Save URLs into either GOOD_URLS or BAD_URLS.
{
  if (match($0, "200 OK$")) {
    for (i = 1; i < NF; i++) {
      if (match($i, "https?://")) {
        GOOD_URLS[$i] = $0;
      }
    }
  } else {
    for (i = 1; i < NF; i++) {
      if (match($i, "https?://")) {
        BAD_URLS[$i] = $0;
      }
    }
  }
}
# Check every URL in BAD_URLS; if it is found in GOOD_URLS a retry was
# successful, otherwise print it.
END {
  for (url in BAD_URLS) {
    if (url in GOOD_URLS == 0) {
      print BAD_URLS[url];
    }
  }
}
