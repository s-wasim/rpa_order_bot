class PageRegistry:
    """Run-scoped registry for Page handles (not serializable, not in state)."""

    def __init__(self):
        self._page = None
        self._context = None

    def set_context(self, context):
        self._context = context

    def get_context(self):
        return self._context

    def set_page(self, page):
        self._page = page

    def get_page(self):
        return self._page

    def close(self):
        if self._context:
            self._context.close()
        self._page = None
        self._context = None


_registry = PageRegistry()


def get_registry():
    return _registry
