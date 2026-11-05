# Signed updates

Every BugOS PC installs its system updates from GitHub Packages (`ghcr.io/253ugursahin/bugos`).
With signing, a PC only installs an update that carries BugOS's signature. If someone gets push access
to GitHub Packages (a leaked token, a hacked account), they still cannot put their own system on every
BugOS PC.

It uses the same method as Universal Blue and Bazzite: [cosign](https://docs.sigstore.dev/) with a key pair.

## How it works

| Part | Where | What it does |
|---|---|---|
| Private key | GitHub secret `SIGNING_SECRET` (and `SIGNING_PASSWORD` if the key has one) | `build.yml` signs every BugOS it pushes. Without the secret it skips this and shows a warning. |
| Public key | `system_files/etc/pki/containers/bugos.pub` | `build.sh` adds a rule to `/etc/containers/policy.json`: images from `ghcr.io/253ugursahin` need this signature. Without the file nothing is checked (as before). |
| Switching over | `bugos-ondertekend.service` | Runs once on every installed PC: moves it from "no check" to "check the signature" (`rpm-ostree rebase ostree-image-signed:...`). It takes effect at the next restart, like an update. |

## Turning it on (once)

Do these in this order. If you add the public key before the CI signs, PCs will refuse every update.

1. Make a key pair on your own computer. Never put the private key in the repo or in a chat.
   ```
   cosign generate-key-pair
   ```
   This makes `cosign.key` (private) and `cosign.pub` (public). A password is optional; if you set one, you need it in step 2.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
   - `SIGNING_SECRET`: the full contents of `cosign.key`
   - `SIGNING_PASSWORD`: the password from step 1 (skip it if you left it empty)
3. Run **Actions → BugOS bouwen → Run workflow** on `main` and check that the "Ondertekenen" step signs without a warning.
4. Only then: copy `cosign.pub` to `system_files/etc/pki/containers/bugos.pub`, commit it and let it build.
   From that build on, PCs check the signature, and installed PCs switch over by themselves.
5. Keep `cosign.key` safe (a password manager). If it leaks, make a new pair and do steps 2 to 4 again.

## Checking it

On a BugOS PC, after a restart:
```
rpm-ostree status
```
The line under "Booted" starts with `ostree-image-signed:docker://ghcr.io/253ugursahin/...`.

## Local test builds

`tools/iso-lokaal.sh` builds an unsigned `:lokaal` image. A PC installed from such a stick (with the key
in it) cannot update from GitHub until it gets a signed image. That is only for testing.
