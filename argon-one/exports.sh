# The GPIO character device has a dynamic major number. 254 is the usual value and only a placeholder
# on boards without the chip.
gpio_major="$(stat -Lc '%t' /dev/gpiochip0 2>/dev/null || true)"
export APP_ARGON_ONE_GPIO_MAJOR="$((16#${gpio_major:-fe}))"
