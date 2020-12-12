"""Define tasks for invoke."""
from invoke import Collection
from . import build_image, digital_ocean

ns = Collection()  # pylint: disable=invalid-name
ns.add_collection(Collection.from_module(build_image))
ns.add_collection(Collection.from_module(digital_ocean, name="ocean"))
