#!/usr/bin/env sh
# Same gate locally and on GitHub Actions. The caller selects an out-of-tree build.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build=${1:-"$root/build"}
configuration=${2:-Debug}
cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE="$configuration"
cmake --build "$build" --parallel 2
python3 "$root/tools/provenance.py" start "$build/provenance.json"
ctest --test-dir "$build" --output-on-failure --output-junit results.xml
python3 "$root/tests/integration/test_scenarios.py" --binary "$build/kestrel_flight" --junit "$build/scenario-results.xml"
python3 "$root/tools/release_check.py" --build "$build" --output "$build/release"
python3 "$root/tools/provenance.py" finish "$build/provenance.json" --junit "$build/results.xml" --junit "$build/scenario-results.xml"
python3 "$root/tools/trace.py" --milestone M5 --junit "$build/results.xml" --provenance "$build/provenance.json"
python3 "$root/tools/dashboard.py" build --output "$build/dashboard" \
    --binary "$build/kestrel_m0" --run-demo \
    --report "$(uname -s) · $configuration=$build/results.xml" \
    --report "$(uname -s) · $configuration scenarios=$build/scenario-results.xml"
