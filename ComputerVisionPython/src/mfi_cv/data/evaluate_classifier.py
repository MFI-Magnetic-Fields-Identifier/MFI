import argparse
import json
from hashlib import file_digest
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from .classifier_dataset import make_demo_dataset, read_dataset
from .motor_classifier import ModelUnavailableError, MotorClassifier


def _classification_metrics(
    labels: list[str], matrix: list[list[int]], top5_hits: int
) -> dict[str, object]:
    total = sum(map(sum, matrix))
    if total == 0:
        raise ValueError("A partição de teste está vazia.")
    per_model = {}
    for index, model in enumerate(labels):
        true_positives = matrix[index][index]
        support = sum(matrix[index])
        predicted = sum(row[index] for row in matrix)
        # Para classes representadas, ausência de predições conta como precisão zero.
        precision = 0.0 if support else None
        if predicted:
            precision = true_positives / predicted
        recall = true_positives / support if support else None
        f1 = 2 * true_positives / (support + predicted) if support else None
        per_model[model] = {
            "support": support, "predicted": predicted,
            "precision": precision, "recall": recall, "f1": f1,
        }
    complete = all(row["support"] for row in per_model.values())
    macro = {
        name: mean(row[name] for row in per_model.values()) if complete else None
        for name in ("precision", "recall", "f1")
    }
    return {
        "top1_accuracy": sum(matrix[index][index] for index in range(len(labels))) / total,
        "top5_accuracy": top5_hits / total if len(labels) >= 5 else None,
        "macro": macro,
        "per_model": per_model,
        "confusion_matrix": {"labels": labels, "rows_are": "actual", "columns_are": "predicted", "counts": matrix},
    }


def evaluate(classifier: MotorClassifier, root: Path) -> dict[str, object]:
    """Avalia o conjunto de teste reservado, sem abrir as imagens de treino ou validação."""
    labels, samples, manifest_hash = read_dataset(root.resolve(), verify_splits=("test",))
    if classifier.manifest_sha256 != manifest_hash or classifier.class_ids != tuple(labels):
        raise ValueError("O manifesto ou a ordem das classes difere do checkpoint treinado.")
    test_samples = samples["test"]
    if not test_samples:
        raise ValueError("A partição de teste está vazia.")

    indices = {label: index for index, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    durations_ms = []
    top5_hits = 0
    for path, actual in test_samples:
        start = perf_counter_ns()
        prediction = classifier.predict(path, top_k=5)
        durations_ms.append((perf_counter_ns() - start) / 1_000_000)
        ranked = [indices[candidate["model_id"]] for candidate in prediction["candidates"]]
        matrix[actual][ranked[0]] += 1
        top5_hits += actual in ranked

    warnings = []
    if classifier.is_demo:
        warnings.append("Demonstração sintética, sem evidência de desempenho em motores reais.")
    if len(labels) < 5:
        warnings.append("Top-5 indisponível com menos de cinco classes.")
    elif len(labels) == 5:
        warnings.append("Top-5 inclui todas as classes e tem pouco valor discriminativo.")
    missing = [label for label, row in zip(labels, matrix, strict=True) if not sum(row)]
    if missing:
        warnings.append(f"Sem fotos de teste para: {', '.join(missing)}. Métricas macro indisponíveis.")

    return {
        "demo": classifier.is_demo,
        "manifest_sha256": manifest_hash,
        "split": "test",
        "image_count": len(test_samples),
        "metrics": _classification_metrics(labels, matrix, top5_hits),
        "inference_time_ms": {
            "mean": mean(durations_ms),
            "median": median(durations_ms),
            "max": max(durations_ms),
            "scope": "cpu_end_to_end_per_photo",
        },
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia o classificador no conjunto de teste reservado.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        classifier = MotorClassifier(args.checkpoint)
        if args.demo != classifier.is_demo:
            raise ValueError("Use --demo com checkpoints sintéticos e --dataset com checkpoints reais.")
        if args.demo:
            with TemporaryDirectory(prefix="mfi-evaluation-demo-") as temp:
                root = Path(temp)
                make_demo_dataset(root)
                report = evaluate(classifier, root)
        else:
            report = evaluate(classifier, args.dataset)
        with args.checkpoint.open("rb") as checkpoint:
            report["checkpoint_sha256"] = file_digest(checkpoint, "sha256").hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(report, output, indent=2, ensure_ascii=False)
            output.write("\n")
    except (OSError, ValueError, ModelUnavailableError, KeyError, TypeError) as error:
        parser.exit(1, f"Erro na avaliação: {error}\n")
    print(args.output)
    for warning in report["warnings"]:
        print(f"Aviso: {warning}")


if __name__ == "__main__":
    main()
