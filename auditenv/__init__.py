"""AuditEnv: reproducible RL environment for an AI financial auditor."""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.2"
GENERATOR_VERSION = "auditenv-gen-" + __version__


def make(config=None, mode: str = "train", **kwargs):
    """Gymnasium-style factory: env = auditenv.make("dev-mixed", mode="eval"); env.reset() uses the
    default seed 0, env.reset(seed=7) another one. Extra kwargs go to AuditEnv."""
    from .env.env import AuditEnv

    return AuditEnv(mode=mode, config=config, **kwargs)
