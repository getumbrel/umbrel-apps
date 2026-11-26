export APP_FCAPTCHA_SIGNING_SECRET="$(derive_entropy 'app-fcaptcha-signing')"
export APP_FCAPTCHA_VERIFY_SECRET="$(derive_entropy 'app-fcaptcha-backend-verification')"

export APP_FCAPTCHA_LITERAL_DOLLAR='$'
