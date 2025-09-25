# HTTP response comparer

Compares HTTP GET responses between two base URLs for a list of paths. Shows a unified diff and optionally writes differing responses to files.

## Usage

Provide a file with one URL path per line (comments and blank lines are ignored):

    /objects
    /objects?id=3&id=5&id=10
    /objects/6
    # this is a comment
    /objects/7

Run with two base URLs and the paths file:

    ./main.py "https://api.restful-api.dev" "https://api.restful-api.dev" paths_to_test.txt

The tool requests each path against both hosts concurrently and compares the responses.

## Parameters

Positional arguments:
- base_url_1: First base URL, e.g. https://api.example.com
- base_url_2: Second base URL, e.g. https://api.example.org
- paths_file: Text file containing the paths to request (one per line)

Options:
- --timeout <seconds> (float, default: 20)
  Per-request timeout used for both hosts.
- --out-dir <path> (default: .)
  Directory where differing response pairs are written.
- --param key=value or --param key (repeatable)
  Adds a query parameter to all requests. You can specify multiple --param flags. A bare key serializes as key= (empty value). Existing query parameters in the paths file are preserved; duplicates are allowed and preserved.
- --header "Name: Value" or --header Name (repeatable)
  Adds a header to all requests to both hosts. A bare name sends the header with an empty value.

## Notes 
- Concurrency: requests to host1 and host2 are fired at the same time using two threads and a barrier to minimize time-based differences.
- Comparison mode: if both responses parse as JSON, a canonicalized JSON diff (sorted keys, pretty-printed) is used; otherwise a text diff is used. Status codes are not directly compared unless there is an error.
- Errors: network/timeout errors are reported, and differing status codes are highlighted in the diff when errors occur.
- Output files: when a difference is detected, two files are written to --out-dir using the pattern:
  YYYYMMDD-HHMMSS_<sanitized-path>_host1.(json|txt) and _host2.(json|txt)
  Each file is prefixed with a single-line comment containing the actual requested URL and headers used by requests, e.g.:
  // {"url": "https://api/...", "headers": {"Authorization": "Bearer ...", ...}}
- Paths file: lines starting with # and blank lines are ignored.
- Exit code: returns 0 if all responses are equal, 1 if any differ.