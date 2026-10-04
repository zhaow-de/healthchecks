# Release notes format

```markdown
## v{version} ({release_date})

### 🚀 Features

#### {short_desc}
{your user-friendly description here}

*[#{number}]({url}) by @{author}*

### 🐛 Bug Fixes
...

### ♻️ Refactoring
...
```

## Input

The data file has two lists:

- `prs`: the pull requests merged into `develop` since the last release. Each entry gets the attribution line `*[#{number}]({url}) by @{author}*`.
- `direct_commits`: commits that reached `develop` without a pull request. Each entry gets the attribution line `*{hash}*`. Skip a commit whose subject ends in `(#<number>)` when that pull request is already in `prs`: it is the same change, merged as a squash.

Both lists carry `type_label`, which names the section the entry belongs in, and `breaking`, which is true when the title or subject carries the `!` marker.

## Section order

Only include sections that have entries:

1. 🚀 Features
2. 🐛 Bug Fixes
3. ♻️ Refactoring
4. 📚 Documentation
5. 🧪 Tests
6. 🔧 CI/Build
7. 📦 Other Changes

## Writing guidelines

For each entry, write a **user-friendly description** that:

- Focuses on **value and impact** for the people who run or use this Healthchecks instance, not on the implementation
- Is understandable by someone who uses the app but is not a developer
- Is 1-2 sentences maximum
- Starts with **Breaking:** when `breaking` is true, and says what whoever runs the instance has to do differently

### By change type

| Type | Focus on... | Example |
|------|-------------|---------|
| Features | What users can now DO | "You can now filter the check list by integration." |
| Fixes | What problem was SOLVED | "Fixed the email integration failing the whole alert run when the SMTP server drops the connection." |
| Refactors | Brief note, mention no user-visible changes | "Internal code improvements for better maintainability. No user-visible changes." |
| CI/Build | What changes for someone who builds or deploys | "Dependencies are now installed with uv; the requirements files are gone." |
