
from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

EXP = Path(r'<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments')
RUN_DIR = Path(r'<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140')
TS = '20260809-222140'
METHOD_ORDER = ['proposed', 'euclidean', 'collision_rejection', 'visibility_graph', 'grid_astar', 'appatt_raw', 'appatt_bspline', 'tig_raw', 'tig_bezier']
ENV_FILES = ['composite_adversarial_001_t04.json', 'composite_adversarial_001_t08.json', 'composite_adversarial_001_t12.json']
LOG_PATH = RUN_DIR / 'logs' / f'composite_adversarial_clean_run_02_{TS}.log'
STATUS_PATH = RUN_DIR / 'logs' / 'run_status.json'
SNAP_DIR = RUN_DIR / 'input_snapshot'
OUTPUT_ROOT = RUN_DIR / 'outputs'

def write_status(payload):
    payload = dict(payload)
    payload['updated_at'] = datetime.now().isoformat(timespec='seconds')
    STATUS_PATH.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')

def append_log(text):
    with LOG_PATH.open('a', encoding='utf-8') as handle:
        handle.write(text)
        if not text.endswith('\n'):
            handle.write('\n')

def completed_row_exists(method, env_id):
    summary = OUTPUT_ROOT / method / 'benchmark_summary.jsonl'
    if not summary.exists():
        return False
    return env_id in summary.read_text(encoding='utf-8', errors='replace')

def main():
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    total = len(METHOD_ORDER) * len(ENV_FILES)
    done = 0
    write_status({'status':'running','done':0,'total':total,'current':None})
    for env_file in ENV_FILES:
        env_path = SNAP_DIR / env_file
        env_id = env_path.stem
        append_log(f'\n=== {env_id} ===')
        for method in METHOD_ORDER:
            if completed_row_exists(method, env_id):
                done += 1
                continue
            write_status({'status':'running','done':done,'total':total,'current':{'environment':env_id,'method':method,'started_at':datetime.now().isoformat(timespec='seconds')}})
            append_log(f'\n--- RUN {env_id} {method} ---')
            cmd = [sys.executable, 'run_benchmark.py', str(env_path), '--method', method, '--output-dir', str(OUTPUT_ROOT / method)]
            start = time.perf_counter()
            with LOG_PATH.open('a', encoding='utf-8', errors='replace') as log:
                proc = subprocess.run(cmd, cwd=str(EXP), stdout=log, stderr=subprocess.STDOUT, text=True)
            elapsed = time.perf_counter() - start
            append_log(f'--- EXIT {proc.returncode} {env_id} {method} elapsed_wall_s={elapsed:.6f} ---')
            done += 1
            write_status({'status':'running','done':done,'total':total,'last':{'environment':env_id,'method':method,'exit_code':proc.returncode,'elapsed_wall_s':elapsed,'finished_at':datetime.now().isoformat(timespec='seconds')}})
            if proc.returncode != 0:
                write_status({'status':'failed','done':done,'total':total,'failed':{'environment':env_id,'method':method,'exit_code':proc.returncode}})
                raise SystemExit(proc.returncode)
    write_status({'status':'done','done':done,'total':total,'finished_at':datetime.now().isoformat(timespec='seconds')})
    append_log('\n=== RUN DRIVER DONE ===')

if __name__ == '__main__':
    main()
