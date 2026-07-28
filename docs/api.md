# Application Programming Interface

The API provided by `djehuty` allows for automating tasks otherwise done
through the user interface, and for gathering additional information such as
statistics on Git repositories.

> **Note:** The full interactive API reference will be available via the
> auto-generated FastAPI documentation once the FastAPI refactor is complete.
> This page covers background context only.

## The v2 API

The `v2` API was designed by [Figshare](https://figshare.com). `djehuty`
implements a backward-compatible version of it, with the following differences:

- The `id` property is superseded by the `uuid` property.
- Error handling is done through precise HTTP error codes, rather than always
  returning `400` on a usage error.

Unless specified otherwise, the HTTP `Content-Type` to interact with the API
is `application/json`. When an API call returns information, set the HTTP
`Accept` header accordingly.

## Authentication

Endpoints under `/v2/account/` require an API token. This token can be obtained
from the dashboard page after logging in, and passed in the `Authorization`
HTTP header:

```
Authorization: token YOUR_TOKEN_HERE
```

## Exploring the API

Two convenient ways to explore the API:

- Use `curl` and `jq` from the command line.
- Open the browser developer tools while performing an action in the web
  interface - the network tab shows the exact API calls being made.
