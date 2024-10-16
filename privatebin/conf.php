;<?php http_response_code(403); /*
; config file for PrivateBin

[main]
; Set a project name to be displayed on the website (optional)
name = "PrivateBin"

; Set the basepath to the local domain
basepath = "http://umbrel.local/"

; Enable discussion feature
discussion = false

; Preselect the discussion feature
opendiscussion = false

; Enable password protection for pastes
password = true

; Disable file uploads (you can enable this if needed)
fileupload = true

; Preselect burn-after-reading feature
burnafterreadingselected = true

; Set the default paste format (plaintext or syntax highlighting)
defaultformatter = "plaintext"

; Set the template (you can choose other templates like "bootstrap-dark" if preferred)
template = "bootstrap5"

; Set a size limit for pastes (here 10 MB)
sizelimit = 52428800

; Disable language selection (as it's a local instance)
languageselection = true

; Default language
languagedefault = "en"

; Enable QR code generation for sharing pastes
qrcode = true

; Let users send an email sharing the paste URL with one click.
; It works both when a new paste is created and when you view a paste.
email = true

[expire]
; Default expiration time for pastes (1 week)
default = "1week"

[expire_options]
; Expiration time options (you can add or modify these)
5min = 300
10min = 600
1hour = 3600
1day = 86400
1week = 604800
1month = 2592000
1year = 31536000
never = 0

[formatter_options]
; Available formatters and their labels
plaintext = "Plain Text"
syntaxhighlighting = "Source Code"
markdown = "Markdown"

[traffic]
; Rate limit between requests from the same IP (10 seconds)
limit = 10

[purge]
; Time between purging expired pastes (in seconds)
limit = 300
; Maximum number of expired pastes to delete per purge
batchsize = 10

[model]
; Data storage model (filesystem for local storage)
class = Filesystem
[model_options]
dir = "data"

[HTTP warnings]
; Enable insecure HTTP warnings
httpwarning = true

[syntax highlighting theme]
; Set a syntax highlighting theme, as found in css/prettify/
; syntaxhighlightingtheme = "sons-of-obsidian"

[Info text to display]
; use single, instead of double quotes for HTML attributes
; info = "More information on the <a href='https://privatebin.info/'>project page</a>."

[Notice to display]
; notice = ""

[URL shortener]
; It is suggested to only use this with self-hosted shorteners as this will leak
; the pastes encryption key.
; urlshortener = "https://shortener.example.com/api?link="
