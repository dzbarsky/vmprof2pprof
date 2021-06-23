# vmprof2pprof

Converts profiles from vmprof (https://vmprof.readthedocs.io/en/latest/) format to pprof (https://github.com/google/pprof)

Example usage:
```
poetry run python vmprof2pprof.py ~/out.vmprof /tmp/out.pprof.gz && ~/go/bin/pprof -http=":" /tmp/out.pprof.gz
```
