"""Export an unmodified view of three real incident time series."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    ("re2ob_checkoutservice_cpu_1", "checkoutservice_cpu", "Surcharge CPU"),
    ("re2ob_recommendationservice_mem_1", "recommendationservice_mem", "Pression mémoire"),
    ("re2ob_currencyservice_delay_1", "currencyservice_latency-90", "Retard réseau : latence observée"),
]

if __name__ == "__main__":
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), layout="constrained")
    for ax, (case, metric, title) in zip(axes, EXAMPLES):
        folder = ROOT / "data/raw/RCAEval" / case
        df = pd.read_parquet(folder / "metrics.parquet")
        injection = int((folder / "inject_time.txt").read_text())
        minutes = (df.time - injection) / 60
        ax.plot(minutes, df[metric], color="#176b87", linewidth=1)
        ax.axvline(0, color="#ce4c40", linestyle="--", label="Injection de panne")
        ax.set_title(f"{title} — {metric}", loc="left")
        ax.set_ylabel("Valeur brute")
        ax.set_xlabel("Minutes par rapport à l'injection")
        ax.grid(alpha=.2)
        ax.legend(loc="upper left")
    fig.suptitle("RCAEval RE2-OB — observations réelles, sans interpolation", fontsize=14)
    (ROOT / "reports").mkdir(exist_ok=True)
    fig.savefig(ROOT / "reports/incident_examples.png", dpi=160)
    fig.savefig(ROOT / "reports/incident_examples.pdf")
    plt.close(fig)
