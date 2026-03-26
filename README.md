# Splight Agent

---

Run components in a remote server

## Versioning

In the first lines of the `pyproject.toml` file, the version is defined as follows:

```
[tool.poetry]
name = "splight-agent"
version = "0.8.5"
```

## Dependencies

The direct dependencies of the project are listed in the `pyproject.toml` file under the `[tool.poetry.dependencies]` section. For example:

```[tool.poetry.dependencies]
python = "^3.x"
```

To bump indirect dependencies, you can use the `[tool.uv]` section in the `pyproject.toml` file accordingly. For example, if you want to update a dependency like `requests`, you would check for the latest version and then update the version in the `pyproject.toml` file:

```

[tool.uv]
constraint-dependencies = [
 # https://splight.atlassian.net/browse/SECUR-397
 "urllib3>=2.6.3",
 # https://splight.atlassian.net/browse/SECUR-518
 "requests>=2.33.0",
]
```