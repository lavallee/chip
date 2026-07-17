"""Single source of truth for the library version and the spec it implements.

``VERSION`` is this Python package's own semantic version. ``SPEC_VERSION`` is
the chip specification schema identifier the models and validators conform to
(chip.spec/v0alpha1). They move independently: a library patch does not bump
the spec identifier.
"""

VERSION = "0.2.0"
SPEC_VERSION = "chip.spec/v0alpha1"
