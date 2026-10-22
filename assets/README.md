# Product listing examples

Each directory contains `request.json` ready for `POST /products/verify`, the
decoded `image.jpg`, `expected-response.json`, and source/license information in
`metadata.json`. The requests contain exactly `title`, `description`, and `images`;
each image is a complete base64 string, not a placeholder or URL.

- `success/1`: blue cotton shirt with matching text and a valid photograph.
  Passes local checks; approval requires a successful AI review. The expected
  response is an expectation, not a recorded live AI decision.
- `fail/1`: the same shirt and valid photograph, with `shit` in the description.
  The current deterministic vocabulary rejects it before any AI request. This
  is an HTTP 200 review rejection, not an HTTP 422 malformed request.
- `fail/2`: title and description advertise a red ceramic coffee mug, but the
  photograph shows a blue shirt. Passes deterministic checks; expected rejection
  is from OpenAI's image–text relevance review. `expected-response.json` gives a
  representative reason; exact AI wording may vary. `actual-response.json` records
  the live response, with verification details in `metadata.json`.

From the repository root, with the API already running:

```bash
curl --fail-with-body http://localhost:8000/products/verify \
  -H 'Content-Type: application/json' \
  --data-binary @assets/success/1/request.json

curl --fail-with-body http://localhost:8000/products/verify \
  -H 'Content-Type: application/json' \
  --data-binary @assets/fail/1/request.json

curl --fail-with-body http://localhost:8000/products/verify \
  -H 'Content-Type: application/json' \
  --data-binary @assets/fail/2/request.json
```

Use your configured host port if it differs from 8000. Submitting `success/1` or
`fail/2` invokes the configured OpenAI reviewer and may incur API charges. Without
a reviewer, these examples return HTTP 503; `fail/1` still rejects
locally. Offline verification uses a reviewer stub for the approval path.

These are synthetic examples for this service, not verified Amazon listings.
The photograph is by Juan de Vojníkov, from
[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Ironed_blue_T-shirt_%28001%29.JPG),
licensed [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
All copies use Wikimedia's 960px thumbnail without further image edits; this
license also applies to the base64 copies. Attribution does not imply endorsement
of either listing's text.
