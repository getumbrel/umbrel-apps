# frozen_string_literal: true

Rails.application.configure do
  config.force_ssl = false
  config.x.use_https = false
  config.action_mailer.default_url_options = {
    host: config.x.web_domain,
    protocol: "http://",
    trailing_slash: false,
  }
  config.x.streaming_api_base_url = "ws://#{config.x.web_domain}"
end
