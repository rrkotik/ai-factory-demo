Seller on amazon
List of products
product-> images, titles, metadata

data verification: deterministict, non-detemrinistic NSWF
business safety


flow: product-> images, titles, metadata -> "submit" -> 
human verification -> going to live / rejected

automation of manual review process

10-20 images max

100k advertisements


API contracts: existing


service -> (product_listing_id, ) -> updated status


Queue / Batch jobs ???

Failure
sql database (product_listing_id, status[awaiting, approved, rejeceted]) -> [http response]
CRON JOB for

success criteria: 
product_listing_id



data verification:
deterministic:
1) image quality/sizes/valid checks
2) text: sanity checks + add the swear vocabulary + vocabulary restricted words + checks title/description sizes


non-detemrinistic
1. image only safety (NSFW checks, vileonce)
2. text only safety, alignment title + description, 
3. combinned image text (relevant)



business safety

## Product listing verification

`POST /products/verify` performs deterministic checks first, then an OpenAI vision
review. It returns a synchronous verdict and does not persist listings or images.

Set `OPENAI_API_KEY` in your local `.env`. The three reviews share these
environment settings (shown with their defaults):

```dotenv
OPENAI_PRODUCT_MODEL=gpt-6-sol
OPENAI_PRODUCT_REASONING_EFFORT=low
```

`gpt-6-sol` supports image inputs, structured outputs, and low reasoning effort
([official model documentation](https://developers.openai.com/api/docs/models/gpt-6-sol)).
Reasoning effort accepts `none`, `low`, `medium`, `high`, `xhigh`, or `max`;
if you change the model, select an effort supported by that model.
Run `make start` after changing environment variables or dependencies.
This uses the official OpenAI Responses API
with image inputs and structured output. Product verification uses OpenAI even
when `EMBEDDING_PROVIDER=local`.

Request (`product.json`; replace the image placeholder with actual base64):

```json
{
  "title": "Blue cotton shirt",
  "description": "A blue short-sleeved cotton shirt.",
  "images": ["<base64-encoded image>"]
}
```

```bash
curl -X POST http://localhost:8000/products/verify \
  -H 'Content-Type: application/json' \
  --data-binary @product.json
```

Raw standard base64 and `data:image/png;base64,...`, `data:image/jpeg;base64,...`,
or `data:image/webp;base64,...` strings are accepted. Images retain their input
order; comments use image numbers starting at 1. The request is also available in
Swagger UI at `/docs`.

Completed reviews return HTTP 200 and exactly one of these forms:

```json
{"status": "approved", "comments": []}
```

```json
{
  "status": "rejected",
  "comments": [
    "Title contains a restricted word: cocaine.",
    "Image 2: Image dimensions must be 256–4096 pixels on each side."
  ]
}
```

### Deterministic checks

- Title: 1–200 characters; description: 1–4,000 characters, after trimming boundary
  whitespace. Both must contain a letter or number. Invisible/control characters
  are rejected; newlines and tabs are allowed within descriptions.
- Vocabulary matching uses Unicode NFKC normalization, case folding, and whole
  words. Small English example vocabularies live in `app/product_verification.py`:
  swear words `fuck`, `shit`; restricted words `cocaine`, `explosives`. These are
  demonstration lists, not comprehensive multilingual or obfuscation detection.
- 1–20 images, JPEG/PNG/WebP only. Strict base64 decoding, actual format and declared
  MIME agreement, file integrity, and full pixel decoding are checked. Animated
  images are rejected.
- Each image: at most 5 MiB decoded, with both sides between 256 and 4096 pixels
  inclusive. All decoded images combined: at most 20 MiB. The HTTP request body
  is capped at 32 MiB before JSON parsing; each encoded image string is also bounded.
- Basic quality heuristics run on grayscale thumbnails of at most 256×256 pixels,
  with transparency composited onto white. Mean brightness below 5 or above 250
  (out of 255), or mean edge strength below 1, rejects the image as too dark,
  too bright, or lacking detail/possibly severely blurred. These demo thresholds
  need calibration against your product photos and can reject minimalist images.

Any deterministic rejection skips OpenAI entirely and returns failure comments.
Invalid JSON, missing/wrongly typed fields, blank or oversized text, invalid image
counts, and request envelope limits return HTTP 422. Image content/quality and
vocabulary failures return HTTP 200 with `status: rejected`.

### OpenAI checks

After deterministic checks pass, three separate OpenAI API calls run in parallel,
using a three-worker `ThreadPoolExecutor` and the synchronous official SDK. The
functions live in `app/product_review.py`:

1. `review_image_safety(images)` receives **only images**. It checks each image for
   sexual content/nudity and violence (including violent acts, graphic injury,
   or promotion of violence).
2. `review_text(product)` sends **only the title and description**. It checks text
   safety (sexual content, hateful abuse, threats, promoted violence, and the example
   restricted product categories) and title–description alignment separately.
3. `review_image_relevance(product, images)` receives **both text and images**.
   It checks whether the title and description are relevant to **each image**.

Every call uses strict Pydantic structured output. Each image-based review must
return exactly one result for every 1-based image index; missing, duplicate, or
unexpected image indexes cause HTTP 503. The text review must return both checks.
All three requests are submitted before waiting, and all workers finish before the
request returns, including on failure. Comments are combined in stable order:
image safety, text safety, title–description alignment, then image relevance.

All checks must pass for approval. A failed check requires a nonblank explanation;
uncertainty is treated as a failed check with an explanation. Listing text and text
inside images are explicitly treated as untrusted data in the review instructions.
This is an AI review, not a guarantee of product authenticity or marketplace compliance.

Missing credentials (after local checks pass), API errors/timeouts in any call, refusals,
incomplete responses, and invalid structured output return generic HTTP 503.
They never become an approval or a fabricated rejection. There is no local AI
fallback. Each call uses a 60-second timeout and at most one retry; the shared client
is closed during application shutdown. Each call allows up to 8,192 output tokens,
including reasoning tokens and per-image results. Three calls are billed separately;
images are sent to both the safety and relevance calls. Requests set `store=false`;
the images and text are still sent to OpenAI for processing. `/ready` checks only the
stores and makes no OpenAI call.

Run `make check` for offline tests, including actual SDK calls against HTTP
transport stubs, and `make integration` for stack checks. No live OpenAI calls are
needed for verification; use `EMBEDDING_PROVIDER=local OPENAI_API_KEY= make integration`
to keep startup and the integration checks credential-free.
# Browser demo and server deployment

The API root (`http://localhost:8000/`, or your configured `API_PORT`) serves the
product verification demo. Expand **Success 1**, **Failure 1**, or **Failure 2**
to inspect and run the corresponding fixture from `assets/`. **Run your case**
accepts a title, description, and multiple images through file selection or drag
and drop. Results show the live approved/rejected decision, rejection comments,
elapsed time, and JSON response. Requests may incur OpenAI API charges.

The public deployment is at <https://romanshv.xyz/ai-factory-demo/> on `ssh nc`.
`deploy/compose.yml` runs the complete stack without development reload or host
ports. Caddy reaches the API through the existing `portal_default` Docker network;
PostgreSQL and Weaviate use a separate backend network. Only the demo assets,
example requests, and product verification endpoint are exposed by
`deploy/demo.caddy`. Existing portal routes retain their original behavior.

Server layout: `/srv/ai-factory-demo/releases/<release>/` for source,
`/srv/ai-factory-demo/current` for the active release, and
`/srv/ai-factory-demo/.env` (mode 600) for the server configuration. The deployment
uses `OPENAI_API_KEY`, `OPENAI_PRODUCT_MODEL`, `OPENAI_PRODUCT_REASONING_EFFORT`,
and a server-specific `POSTGRES_PASSWORD`. Keys are never included in browser
assets or Docker build context. One API worker is used, with a concurrency bound
of 16; this is a public demo, not a per-user usage or billing quota.

After uploading a new release, run on the server:

```bash
cd /srv/ai-factory-demo/current
docker compose --env-file /srv/ai-factory-demo/.env -f deploy/compose.yml up --build -d --wait --wait-timeout 240
docker compose --env-file /srv/ai-factory-demo/.env -f deploy/compose.yml ps
```

The Caddy snippet is imported inside the bare-domain site. Its existing redirect
to `home.romanshv.xyz` belongs in a fallback `handle` block, so it does not intercept
demo requests. Validate and reload Caddy after editing its configuration:

```bash
docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

To roll back an application release, point `current` at the previous release and
run the same Compose command. Keep the existing named volumes; do not delete them.
