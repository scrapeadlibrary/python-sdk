"""Typed response models.

Every model is a dataclass built with ``Model.from_dict(...)``. Parsing is tolerant: unknown fields
are ignored (but kept in ``raw``), missing fields default to ``None`` / empty lists, so a newer API
version never breaks an older SDK.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, TypeVar

T = TypeVar("T", bound="Model")


@dataclass
class Model:
    """Base class: tolerant construction from API JSON."""

    # field name -> (model class, is_list)
    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {}

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any] | None) -> T:
        if not isinstance(data, dict):
            data = {}
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cls):
            if f.name == "raw" or f.name not in data:
                continue
            value = data[f.name]
            nested = cls._nested.get(f.name)
            if nested is not None and value is not None:
                model_cls, is_list = nested
                if is_list:
                    value = [model_cls.from_dict(v) for v in value if isinstance(v, dict)]
                elif isinstance(value, dict):
                    value = model_cls.from_dict(value)
            kwargs[f.name] = value
        return cls(raw=data, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        """The original JSON object returned by the API (including unknown fields)."""
        return self.raw


# ---------------------------------------------------------------------------
# Ad building blocks
# ---------------------------------------------------------------------------


@dataclass
class CallToAction(Model):
    text: str | None = None
    type: str | None = None


@dataclass
class AdPage(Model):
    """The advertiser page, as embedded in an ad."""

    id: str = ""
    name: str | None = None
    profile_picture_url: str | None = None
    is_person: bool = False
    categories: list[str] = field(default_factory=list)
    like_count: int | None = None


@dataclass
class Media(Model):
    """An image or video. URLs are signed CDN links that expire at ``expires_at``."""

    type: str | None = None  # "image" | "video"
    url: str | None = None
    preview_url: str | None = None
    sd_url: str | None = None
    expires_at: str | None = None


@dataclass
class Card(Model):
    """One card of a carousel ad."""

    title: str | None = None
    body: str | None = None
    caption: str | None = None
    link_url: str | None = None
    cta: CallToAction | None = None
    image: Media | None = None
    video: Media | None = None

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        "cta": (CallToAction, False),
        "image": (Media, False),
        "video": (Media, False),
    }


@dataclass
class Spend(Model):
    lower: int | None = None
    upper: int | None = None
    currency: str | None = None
    text: str | None = None


@dataclass
class RangeText(Model):
    text: str | None = None


@dataclass
class PoliticalInfo(Model):
    """Spend, impressions and reach of political & issue ads."""

    spend: Spend | None = None
    impressions: RangeText | None = None
    reach: RangeText | None = None
    disclaimer: str | None = None

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        "spend": (Spend, False),
        "impressions": (RangeText, False),
        "reach": (RangeText, False),
    }


@dataclass
class Ad(Model):
    """An ad as returned by list endpoints."""

    id: str = ""
    url: str | None = None
    page: AdPage | None = None
    status: str | None = None  # "active" | "inactive"
    started_at: str | None = None
    ended_at: str | None = None
    platforms: list[str] = field(default_factory=list)
    format: str | None = None  # image | video | carousel | dco | dpa | text | other
    body: str | None = None
    title: str | None = None
    caption: str | None = None
    link_url: str | None = None
    link_description: str | None = None
    cta: CallToAction | None = None
    images: list[Media] = field(default_factory=list)
    videos: list[Media] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    variants_count: int | None = None
    collation_id: str | None = None
    categories: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    political: PoliticalInfo | None = None
    contains_ai_generated_media: bool | None = None

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        "page": (AdPage, False),
        "cta": (CallToAction, False),
        "images": (Media, True),
        "videos": (Media, True),
        "cards": (Card, True),
        "political": (PoliticalInfo, False),
    }

    @property
    def is_active(self) -> bool:
        return self.status == "active"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@dataclass
class InstagramAccount(Model):
    username: str | None = None
    followers: int | None = None
    verified: bool | None = None


@dataclass
class Page(Model):
    """An advertiser page profile."""

    id: str = ""
    name: str | None = None
    is_person: bool = False
    category: str | None = None
    like_count: int | None = None
    instagram: InstagramAccount | None = None
    verified: bool | None = None
    profile_picture_url: str | None = None
    cover_photo_url: str | None = None
    about: str | None = None
    deleted: bool = False
    active_ads_estimate: int | None = None
    url: str | None = None

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        "instagram": (InstagramAccount, False),
    }


@dataclass
class PageSummary(Model):
    """An advertiser found by ``pages.search``."""

    id: str = ""
    name: str | None = None
    is_person: bool = False
    profile_picture_url: str | None = None
    categories: list[str] = field(default_factory=list)
    like_count: int | None = None
    ads_in_results: int | None = None


# ---------------------------------------------------------------------------
# Ad detail
# ---------------------------------------------------------------------------


@dataclass
class Payer(Model):
    """Who paid for the ad and who benefits. Natural persons are pseudonymised
    (``"person:<hash>"``)."""

    payer: str | None = None
    beneficiary: str | None = None


@dataclass
class TargetLocation(Model):
    name: str | None = None
    type: str | None = None
    excluded: bool = False


@dataclass
class AudienceBreakdown(Model):
    country: str | None = None
    age_range: str | None = None
    male: int | None = None
    female: int | None = None
    unknown: int | None = None


@dataclass
class RegionTransparency(Model):
    """EU (DSA) or UK transparency data: reach, targeting and audience breakdown."""

    reach: int | None = None
    gender: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    locations: list[TargetLocation] = field(default_factory=list)
    breakdown: list[AudienceBreakdown] = field(default_factory=list)

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        "locations": (TargetLocation, True),
        "breakdown": (AudienceBreakdown, True),
    }


@dataclass
class Transparency(Model):
    eu: RegionTransparency | None = None
    uk: RegionTransparency | None = None

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        "eu": (RegionTransparency, False),
        "uk": (RegionTransparency, False),
    }


@dataclass
class AdDetail(Ad):
    """Full ad detail: the list fields plus advertiser, payers and transparency."""

    advertiser: Page | None = None
    payers: list[Payer] = field(default_factory=list)
    transparency: Transparency | None = None
    about: str | None = None
    removed: bool = False

    _nested: ClassVar[dict[str, tuple[type[Model], bool]]] = {
        **Ad._nested,
        "advertiser": (Page, False),
        "payers": (Payer, True),
        "transparency": (Transparency, False),
    }


# ---------------------------------------------------------------------------
# Response envelopes
# ---------------------------------------------------------------------------

ItemT = TypeVar("ItemT", bound=Model)


@dataclass
class _Envelope:
    credits_used: int = 0
    cached: bool = False
    credits_remaining: int | None = None
    """From the ``X-Credits-Remaining`` header."""


@dataclass
class ListPage(_Envelope, Generic[ItemT]):
    """One page of results. Iterate it directly to get the items."""

    data: list[ItemT] = field(default_factory=list)
    total_estimate: int | None = None
    has_more: bool = False
    next_cursor: str | None = None
    media_expires_at: str | None = None

    def __iter__(self) -> Iterator[ItemT]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)


@dataclass
class AdsPage(ListPage[Ad]):
    """A page of ads from ``ads.search`` or ``pages.ads``."""

    @classmethod
    def from_response(cls, body: dict[str, Any], credits_remaining: int | None) -> AdsPage:
        return cls(
            data=[Ad.from_dict(a) for a in body.get("data") or [] if isinstance(a, dict)],
            total_estimate=body.get("total_estimate"),
            has_more=bool(body.get("has_more")),
            next_cursor=body.get("next_cursor"),
            credits_used=body.get("credits_used") or 0,
            cached=bool(body.get("cached")),
            media_expires_at=body.get("media_expires_at"),
            credits_remaining=credits_remaining,
        )


@dataclass
class PageSearchResult(ListPage[PageSummary]):
    """Advertisers returned by ``pages.search``."""

    @classmethod
    def from_response(cls, body: dict[str, Any], credits_remaining: int | None) -> PageSearchResult:
        return cls(
            data=[PageSummary.from_dict(p) for p in body.get("data") or [] if isinstance(p, dict)],
            credits_used=body.get("credits_used") or 0,
            cached=bool(body.get("cached")),
            credits_remaining=credits_remaining,
        )


@dataclass
class AdDetailResponse(_Envelope):
    """Response of ``ads.get``: the ad is in ``data``."""

    data: AdDetail = field(default_factory=AdDetail)
    media_expires_at: str | None = None

    @classmethod
    def from_response(cls, body: dict[str, Any], credits_remaining: int | None) -> AdDetailResponse:
        return cls(
            data=AdDetail.from_dict(body.get("data")),
            credits_used=body.get("credits_used") or 0,
            cached=bool(body.get("cached")),
            media_expires_at=body.get("media_expires_at"),
            credits_remaining=credits_remaining,
        )


@dataclass
class PageResponse(_Envelope):
    """Response of ``pages.get``: the page is in ``data``."""

    data: Page = field(default_factory=Page)

    @classmethod
    def from_response(cls, body: dict[str, Any], credits_remaining: int | None) -> PageResponse:
        return cls(
            data=Page.from_dict(body.get("data")),
            credits_used=body.get("credits_used") or 0,
            cached=bool(body.get("cached")),
            credits_remaining=credits_remaining,
        )
