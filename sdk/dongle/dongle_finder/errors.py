class DongleNotFoundError(RuntimeError):
    """Raised when no matching dongle could be found."""
    pass


class MultipleDonglesError(RuntimeError):
    """Raised when more than one matching dongle is found."""
    def __init__(self, message, devices):
        super().__init__(message)
        self.devices = devices  # list[DongleInfo] but avoid circular imports
