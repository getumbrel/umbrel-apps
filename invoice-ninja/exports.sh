# Generate a new APP_KEY
export NEW_APP_KEY=$(docker run --rm -it invoiceninja/invoiceninja php artisan key:generate --show)