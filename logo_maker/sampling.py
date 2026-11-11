"""Bounded sampling decisions. Evidence describes pixels; code chooses one control."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Settings:
    cap: int = 4096
    threshold: float = 0.01
    minimum: int = 0
    seed: int = 0
    adaptive: bool = True

    def quality(self) -> dict:
        return {
            "samples": self.cap,
            "adaptive_threshold": self.threshold,
            "min_samples": self.minimum,
            "seed": self.seed,
            "adaptive": self.adaptive,
        }

    @classmethod
    def from_quality(cls, quality: dict) -> Settings:
        return cls(
            cap=quality["samples"],
            threshold=quality["adaptive_threshold"],
            minimum=quality.get("min_samples", 0),
            seed=quality.get("seed", 0),
            adaptive=quality["adaptive"],
        )


@dataclass(frozen=True)
class Decision:
    state: str
    reason: str
    settings: Settings | None = None

    def record(self) -> dict:
        return asdict(self)


def decide(
    current: Settings,
    diagnosis: dict | None,
    *,
    source_key: str,
    image_sha256: str,
    diagnostics: dict,
    overrides: dict,
    attempts_left: int,
    seconds_left: float,
    estimated_seconds: float | None,
) -> Decision:
    """Select one bounded comparison from reviewed, revision-bound noise evidence.

    The 95%-of-cap boundary describes resource saturation, not a noise tolerance.
    Observed near-cap pixels in the reviewed region warrant a cap hypothesis rather than changing
    threshold simultaneously. Visual acceptance is supplied independently.
    """
    if not diagnosis:
        return Decision("unknown", "no image-bound diagnosis; generic edge failure is insufficient")
    if diagnosis.get("source_key") != source_key or diagnosis.get("image_sha256") != image_sha256:
        return Decision("unknown", "stale diagnosis: changed inputs, settings, seed or image")
    kind = diagnosis.get("kind")
    if kind in {
        "geometry",
        "typography",
        "filtering",
        "alpha",
        "resolution",
        "denoiser_detail_loss",
    }:
        return Decision("refinement_needed", f"{kind} requires scoped authoring under #3")
    if kind != "sampling_noise":
        return Decision("unknown", "uncertain diagnosis is not permission to increase sampling")
    seeds = diagnosis.get("independent_seeds", [])
    if (
        len(set(seeds)) < 2
        or current.seed not in seeds
        or diagnosis.get("noisy_and_denoised_reviewed") is not True
        or not diagnosis.get("basis")
    ):
        return Decision("unknown", "noise needs independent seeds and noisy/denoised detail review")
    regions = diagnostics.get("regions", {})
    region = diagnosis.get("region")
    if not isinstance(region, str) or region not in regions:
        return Decision("unknown", "noise diagnosis must name a reviewed diagnostic region")
    reviewed_region = regions.get(region) or {}
    saturation = reviewed_region.get("near_cap_fraction")
    if diagnostics.get("status") != "available" or saturation is None or not current.adaptive:
        return Decision("unknown", "adaptive sample diagnostics missing or unavailable")
    import math

    if (
        not isinstance(saturation, (int, float))
        or not math.isfinite(saturation)
        or not 0 <= saturation <= 1
        or diagnostics.get("cap", current.cap) != current.cap
    ):
        return Decision("unknown", "invalid sample diagnostics or cap mismatch")
    if saturation > 0:
        if current.cap >= 8192:
            return Decision("cap_limit", "comparison ceiling reached; no convergence claimed")
        target = replace(current, cap=min(current.cap * 2, 8192))
        control = "max_samples"
    else:
        if current.threshold <= 0.001:
            return Decision("quality_unresolved", "threshold comparison floor reached")
        target = replace(current, threshold=max(current.threshold / 2, 0.001))
        control = "adaptive_threshold"
    if control in overrides:
        return Decision("override_conflict", f"explicit render.{control} prevents this repair")
    if attempts_left <= 0:
        return Decision("attempt_limit", "no comparison attempts remain")
    if estimated_seconds is None or seconds_left <= estimated_seconds:
        return Decision(
            "time_limit", "insufficient measured whole-attempt cost and remaining budget"
        )
    return Decision("compare", f"test only {control}; visual acceptance still required", target)


def qualify_profile(profile: dict | None, context: dict) -> tuple[str, str]:
    """Fail closed on stale context or missing owner-reviewed qualification evidence.

    A profile is a manually reviewed provenance artifact, not an automatic claim
    that an image metric measures craft. File hashes make missing/mutated reviews
    visible. Profile creators are responsible for truthful owner labels.
    """
    import hashlib
    import math
    from pathlib import Path

    if not profile or profile.get("schema") != 1:
        return "profile_unqualified", "no qualified replacement; retain baseline"
    machine_scope = {
        k: v for k, v in context.items() if k not in {"material_presets", "custom_scene_sha256"}
    }
    if profile.get("context") != machine_scope:
        return "profile_stale", "machine/build/stage/settings scope changed"
    if not set(context.get("material_presets", [])) <= set(profile.get("material_presets", [])):
        return "profile_out_of_scope", "material preset outside reviewed transfer scope"
    if "custom_scene_sha256" in context:
        return (
            "profile_out_of_scope",
            "custom bpy dependency inventory is unknown; source hash alone is insufficient",
        )
    if profile.get("owner_review") != "approved":
        return "profile_unqualified", "owner visual qualification pending"
    if not {"matte", "metal", "glass", "dark", "typography", "alpha"} <= set(
        profile.get("coverage", [])
    ):
        return "profile_unqualified", "cross-material coverage incomplete"
    cases = profile.get("cases", [])
    if not {"positive", "degraded", "held_out"} <= {c.get("role") for c in cases}:
        return "profile_unqualified", "reviewed controls and held-out brief required"
    for case in cases:
        evidence = case.get("evidence", {})
        path = Path(evidence.get("path", ""))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence.get(
            "sha256"
        ):
            return "profile_unqualified", "qualification evidence missing or changed"
    costs = profile.get("job_costs", [])
    if not costs or any(
        not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key]) or row[key] <= 0
        for row in costs
        for key in ("baseline_seconds", "candidate_seconds")
    ):
        return "profile_unqualified", "complete baseline/candidate job costs required"
    settings = profile.get("settings", {})
    try:
        validate_settings(Settings.from_quality(settings))
    except (KeyError, TypeError, ValueError):
        return "profile_unqualified", "invalid profile settings"
    return "qualified", "reviewed profile matches this execution scope"


def validate_settings(settings: Settings) -> None:
    import math

    if (
        type(settings.cap) is not int
        or not 1 <= settings.cap <= 1048576
        or type(settings.minimum) is not int
        or not 0 <= settings.minimum <= settings.cap
        or type(settings.seed) is not int
        or not 0 <= settings.seed <= 2147483647
        or type(settings.adaptive) is not bool
        or not math.isfinite(settings.threshold)
        or not 0 <= settings.threshold <= 1
    ):
        raise ValueError("invalid sampling cap/minimum/seed/adaptive/threshold")


class SamplingLimit(RuntimeError):
    """A technical budget ended; a prior artifact may still be usable."""


class Budget:
    """A shared monotonic whole-job deadline and native-attempt ceiling."""

    def __init__(
        self,
        wall_seconds: float = 1800,
        attempt_limit: int = 2,
        *,
        clock=None,
        parent: Budget | None = None,
        started_at: float | None = None,
    ):
        import math
        import time

        if not math.isfinite(wall_seconds) or wall_seconds <= 0 or not 1 <= attempt_limit <= 64:
            raise ValueError("sampling budget requires positive seconds and 1..64 attempts")
        self.parent = parent
        self.clock = clock or (parent.clock if parent else time.monotonic)
        if started_at is not None and not math.isfinite(started_at):
            raise ValueError("sampling budget requires a finite start time")
        self.started = self.clock() if started_at is None else started_at
        self.deadline = (
            min(self.started + wall_seconds, parent.deadline)
            if parent
            else self.started + wall_seconds
        )
        self.wall_seconds = wall_seconds
        self.attempt_limit = attempt_limit
        self.attempts = 0

    @property
    def remaining(self) -> float:
        return max(0, self.deadline - self.clock())

    def check(self) -> None:
        if self.remaining <= 0:
            raise SamplingLimit("time_limit: whole-job deadline exhausted")

    def begin_attempt(self) -> int:
        self.check()
        if self.attempts >= self.attempt_limit:
            raise SamplingLimit("attempt_limit: native attempts exhausted (including crashes)")
        if self.parent:
            self.parent.begin_attempt()
        self.attempts += 1
        return self.attempts

    def record(self) -> dict:
        return {
            "wall_seconds": self.wall_seconds,
            "attempt_limit": self.attempt_limit,
            "attempts": self.attempts,
            "elapsed_seconds": self.clock() - self.started,
            "remaining_seconds": self.remaining,
            "scope": "whole host job including setup, probes, denoise and output",
        }


def sampling_qualified(report: dict) -> bool:
    """Production sampling eligibility is separate from creative acceptance."""
    return (
        report.get("profile", {}).get("state") == "qualified"
        and report.get("outcomes", {}).get("sampling") == "profile_baseline"
    )
