from datetime import date, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Float, Index, Integer, String

from app.core.database import Base


class Place(Base):
    """
    A place in a city's catalogue, built offline from open data (#119):
    Overture Maps places and Foursquare OS Places. Google is only used to
    match a place ID (#120) and to check the final Stops live (#93); no
    Google field is stored here except that ID.
    """

    __tablename__ = "places"

    id = Column(Integer, primary_key=True)
    city = Column(String(40), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    area_id = Column(String(60), nullable=True)  # Area slug (app/data/areas), null outside every Area
    categories = Column(JSON, nullable=False, default=list)  # source categories (Overture taxonomy, Foursquare ids)
    interests = Column(JSON, nullable=False, default=list)  # Interest keys (app/data/interests.yaml)
    overture_id = Column(String(64), nullable=True, unique=True)
    fsq_id = Column(String(64), nullable=True, unique=True)
    confidence = Column(Float, nullable=True)  # Overture's existence confidence
    website = Column(String(500), nullable=True)
    google_place_id = Column(String(300), nullable=True, index=True)  # set by the matching job (#120)
    google_matched_at = Column(DateTime, nullable=True)
    skip_until = Column(Date, nullable=True)  # don't retry matching before this (#120)
    first_seen = Column(Date, nullable=False, default=date.today)
    last_seen = Column(Date, nullable=False, default=date.today)
    last_seen_release = Column(String(40), nullable=True)
    missed_releases = Column(Integer, nullable=False, default=0)  # deleted at 2 in a row
    last_missed_release = Column(String(40), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_places_city_area", "city", "area_id"),)
