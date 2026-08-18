from jinja2 import Environment
from loguru import logger
from nicegui import ui

from beaverhabits.configs import settings

PREVENT_CONTEXT_MENU = """\
document.body.style.webkitTouchCallout='none';

document.addEventListener('contextmenu', function(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
});
"""

FIX_ZOOM_POSITIONS = """\
// Quasar positions fixed overlays (menus, dialogs, tooltips, notifications)
// with viewport coordinates, but the theme sets body { zoom: 1.5 }, which
// rescales those coordinates by the zoom factor and shifts the overlay away
// from its anchor. Compensate by dividing the inline offsets by the zoom.
(function () {
  // Quasar's position engine compares anchor coordinates (already zoomed by
  // getBoundingClientRect) against document.body.clientWidth, which CSS zoom
  // leaves unzoomed. That mismatch flips menus that are still on screen.
  // Report the true viewport width instead, so the engine's boundary math
  // works in the same (zoomed) coordinate space as the anchors.
  if (Object.getOwnPropertyDescriptor(document.body, 'clientWidth') === undefined) {
    Object.defineProperty(document.body, 'clientWidth', {
      configurable: true,
      get: function () {
        return window.innerWidth;
      },
    });
  }

  const corrected = new WeakMap();
  function fixZoomPositions() {
    const zoom = parseFloat(getComputedStyle(document.body).zoom);
    if (!zoom || zoom === 1) return;
    const factor = 1 / zoom;
    const targets = document.querySelectorAll(
      '.q-menu, .q-dialog, .q-tooltip, .q-notification'
    );
    targets.forEach((el) => {
      const style = el.style;
      let prev = corrected.get(el);
      if (!prev) {
        prev = {};
        corrected.set(el, prev);
      }
      ['left', 'top', 'width', 'height'].forEach((prop) => {
        const value = style[prop];
        if (!value || prev[prop] === value) return;
        const num = parseFloat(value);
        if (Number.isNaN(num)) return;
        style[prop] = num * factor + 'px';
        prev[prop] = style[prop];
      });
    });
  }
  new MutationObserver(fixZoomPositions).observe(document.body, {
    attributes: true,
    subtree: true,
    attributeFilter: ['style'],
  });
})();
"""

UNHOVER_CHECKBOXES = """\
const elements = document.querySelectorAll('.q-checkbox');

elements.forEach(element => {
  const mouseOutEvent = new Event('mouseout');
  element.addEventListener('mouseout', () => {
    element.dispatchEvent(mouseOutEvent);
  });
});
"""

PADDLE_JS_TEMPLATE = """\
<script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
<script type="text/javascript">
  Paddle.Initialize({ 
    token: '{{paddle_token}}' 
  });
  {% if sandbox %}Paddle.Environment.set("sandbox");{% endif %}

  function getPrices() {
    console.log('start...');
    var request = {
        items: [{ quantity: 1, priceId: '{{price_id}}' }]
    };
    console.log(request);
    Paddle.PricePreview(request)
      .then((result) => {
        console.log(result);
      })
      .catch((error) => {
        console.error(error);
      });
  }

  // open checkout
  // https://developer.paddle.com/build/checkout/build-overlay-checkout
  function openCheckout(email) {
    customer = {}
    if (email) {
      customer.email = email;
    }
    console.log(customer);
    Paddle.Checkout.open({
      items: [{ priceId: "{{price_id}}", quantity: 1 }],
      customer: customer,
      settings: {
        theme: "dark",
      }
    });
  }
</script>
"""

env = Environment()
PADDLE_JS = env.from_string(PADDLE_JS_TEMPLATE).render(
    paddle_token=settings.PADDLE_CLIENT_SIDE_TOKEN,
    sandbox=settings.PADDLE_SANDBOX,
    product_id=settings.PADDLE_PRODUCT_ID,
    price_id=settings.PADDLE_PRICE_ID,
)


def prevent_context_menu():
    logger.info("Run javascript to prevent context menu for iOS")
    ui.run_javascript(PREVENT_CONTEXT_MENU)


def unhover_checkboxes():
    ui.run_javascript(UNHOVER_CHECKBOXES)


def show_icons():
    logger.info("Showing icons in the menu")
    ui.run_javascript(
        """
        const icons = document.querySelectorAll('.theme-icon-lazy');
        icons.forEach(icon => {
            icon.classList.remove("invisible");
        });
        """
    )


async def force_checkbox_blur():
    # Resolve ripple issue
    # https://github.com/quasarframework/quasar/blob/dev/ui/src/components/checkbox/QCheckbox.sass
    await ui.run_javascript(
        """
       const checkboxes = document.querySelectorAll('.q-checkbox');
       checkboxes.forEach(checkbox => {checkbox.blur()});
       """
    )
