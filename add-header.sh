#!/bin/bash

#
boilerplate="# Copyright [2025] [SOPTIM AG]
#
# Licensed under the Apache License, Version 2.0 (the \"License\");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an \"AS IS\" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"

# Only check newly added or modified Python files
files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')

for file in $files; do
  if [ -f "$file" ] && ! grep -q "Licensed under the Apache License" "$file"; then
    echo -e "$boilerplate\n$(cat "$file")" > "$file"
    echo "Boilerplate added to: $file"
    changed=1
  fi
done

# Fail the hook if any file was changed
if [ "$changed" -eq 1 ]; then
  echo "License header(s) added. Please stage the changes and commit again."
  exit 1
fi
