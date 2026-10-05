import uuid

from pydantic import BaseModel


class LocationCluster(BaseModel):
    # Reverse geocoding (turning lat/lon into "Lucknow", "Delhi", etc.) needs
    # an external API -- both Nominatim and BigDataCloud returned 403 from
    # this sandbox's network allow-list when checked during development, the
    # same class of block as Hugging Face/OpenAI. So this groups by rounded
    # coordinates ("approximate area") rather than a real place name.
    # location_name carries through PhotoMetadata.location_name for photos
    # where a real place name was set some other way (e.g. manually, or a
    # future geocoding integration), and is null otherwise.
    latitude: float
    longitude: float
    location_name: str | None
    photo_count: int
    sample_photo_id: uuid.UUID
