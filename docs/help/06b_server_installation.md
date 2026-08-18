# Installing and running the server

**The deployment guides in `docs/deployment/` are the single source of truth for
installing TinyMRP.** They are written to be read on GitHub before you have a
server, they are the pages the installers themselves refer to, and they are the
only place install steps are maintained. This page does not repeat them — it
tells you which one to open, and then gives you the two tables that are
generated from the code and so cannot be kept anywhere else.

If someone sent you here to install a server, the page you want is almost
certainly **`docs/deployment/01-vm-docker.md`**.

## Which guide

| You have | Open |
| --- | --- |
| **A Linux VM or server with Docker — the recommended path** | **`docs/deployment/01-vm-docker.md`** |
| Windows with Docker Desktop | `docs/deployment/01-vm-docker.md`, "Windows Docker Desktop" section |
| A Linux server where Docker is not permitted | `docs/deployment/02-linux-bare-metal.md` |
| A Windows machine on an office LAN | `docs/deployment/03-windows-lan.md` |
| A locked-down Windows host where only `python run.py` is approved | `docs/deployment/12-restricted-windows-flask.md` |
| A public VPS hosting several companies | `docs/deployment/04-vps-multi-instance.md` |
| A developer machine | `docs/deployment/09-local-development.md` |

Each guide is self-contained: prerequisites, the install command, what every
question means, first login, day-to-day operation, and the failures specific to
that path. You should not need to read two of them.

## Then, whichever path you took

| Question | Page |
| --- | --- |
| What does this environment variable do? | `docs/deployment/05-configuration-reference.md` |
| How do I log in, seed roles, load the sample dataset? | `docs/deployment/06-first-run.md` |
| Something is broken | `docs/deployment/07-troubleshooting.md` |
| Addresses, firewalls, TLS, adding HTTPS to a LAN | `docs/deployment/08-networking-and-tls.md` |
| Backups, updates, uninstall | `docs/deployment/10-operations.md` |
| The question people actually ask | `docs/deployment/11-faq.md` |

## The recommended path in brief

On a Linux VM with Docker, from a clone:

```bash
./deploy/community/install.sh --build
```

Add `--with-demo-data` to load the CV03 sample dataset and one login per role
for evaluation; leave it off for an instance that will hold real data.

It asks for a deliverables folder, an access mode with its address, and the
first administrator, and generates every secret itself. Afterwards:

```bash
./deploy/community/tinymrp.sh status|logs|reconfigure|backup|restore|update|uninstall
```

`reconfigure` is how you change the address, port or access mode later. Do not
hand-edit `.env`: eight keys have to agree, and when they disagree the symptom
is a silent login loop rather than an error.

`update` picks up new code without reinstalling. On an instance installed from
a git checkout, run it with **no argument** — it pulls, rebuilds, swaps the app
container over, backs up first and rolls back if the new build does not come
up. On an instance installed from a release bundle, give it the version to move
to: `./deploy/community/tinymrp.sh update v2.1.0`. Neither touches your
database, your deliverables or your `.env`.

The one setting that decides whether a deployment works at all is
`TINYMRP_URL` — the address users type, **scheme included**. Its scheme is what
tells the app whether to mark session cookies `Secure`. Declaring `https://` on
a plain-HTTP deployment makes every login bounce back to the login form.
`reconfigure` derives it for you, which is the reason it exists.

## Every deployment script and its options

Generated from the scripts themselves, so it cannot drift from what they
actually accept. Run any of them with `--help` or `Get-Help` for full detail.

{{AUTO_DEPLOY_SCRIPTS}}

## Every configuration variable

Collected from the shipped `.env*.example` templates.

{{AUTO_ENV_VARS}}
