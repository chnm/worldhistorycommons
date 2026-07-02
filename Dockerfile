# syntax=docker/dockerfile:1.7

FROM stagex/pallet-nodejs AS build-stage

# stagex/user-hugo-extended ships the binary inside a directory at
# /usr/bin/hugo/, named "hugo_exended" (sic — the missing 'x' is upstream's).
# Copying the dir itself would make /usr/local/bin/hugo a directory, which
# then fails `RUN hugo` with "Permission denied". Copy the actual file.
COPY --from=stagex/user-hugo-extended /usr/bin/hugo/hugo_exended /usr/local/bin/hugo

ARG hugobuildargs
ENV HUGO_BUILD_ARGS=$hugobuildargs

WORKDIR /app

# Install the pinned Pagefind toolchain first so this layer caches independently
# of content changes. package-lock.json pins pagefind + its platform binary.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN hugo ${HUGO_BUILD_ARGS}
# Build the Pagefind search index over the whole site. Content lives at the
# site root (/{slug}) — there is no items/ subtree — so index everything Hugo
# emitted under public/. --no-install uses the pagefind installed by `npm ci`.
RUN npx --no-install pagefind --site public

FROM stagex/user-caddy

COPY --from=stagex/core-musl / /
COPY --from=build-stage /app/public /srv

COPY <<'EOF' /etc/caddy/Caddyfile
{
	auto_https off
	admin off
}

:80 {
	root * /srv
	encode gzip zstd

	# Legacy Drupal URL redirects (301). `map` + `redir` are ordered by Caddy
	# ahead of `file_server`, so matched /node/{id} paths redirect before a 404.
	# redirects.caddy is generated into Hugo's static/, so it ships inside public/
	# (the release artifact) and lands here at /srv/redirects.caddy on build.
	# Regenerate with `just redirects`. See docs/REDIRECTS.md.
	import /srv/redirects.caddy

	file_server
}
EOF

ENV XDG_CONFIG_HOME=/tmp/caddy-config \
    XDG_DATA_HOME=/tmp/caddy-data

EXPOSE 80
ENTRYPOINT ["/usr/bin/caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
