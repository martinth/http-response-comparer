# HTTP response comparer

Compares JSON GET requests between different hosts.

## Usage

You can give it a list of URL paths in a file like `paths_to_test.txt` like so:

    /objects
    /objects?id=3&id=5&id=10
    /objects/6
    /objects/7

And then invoke it with two separate base URLs as and the file as parameters, like so (in practice the base URLs should 
be different, this is just as example):

    ./main.py "https://api.restful-api.dev" "https://api.restful-api.dev" paths_to_test.txt 

It will then invoke each given path on both base URLs simultaneously and compare the response. Any difference will be
logged in a clear diff, and the responses will also be written to a file in the current directory for inspection.

### Common parameters

You can add common parameters all outgoing requests, options are:

    ./main.py --param="foo=bar" --param debug

Will add all the "param" flags as GET parameter to all outgoing requests (it will add to existing parameter that might
be given in the `paths_to_test.txt` file).

You can add also add header parameters:

    ./main.py --header="Authorization: Bearer 123"

Which will be added as headers to all requests.