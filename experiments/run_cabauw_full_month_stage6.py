"""run verified stage 5 conversion and stage 6 observational evaluation for a full monthly file."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experiments.run_knmi_cabauw_stage5 import execute as stage5
from experiments.evaluate_cabauw_stage6 import run as stage6
from experiments.inspect_cabauw_quality_metadata import run as inventory


def execute(netcdf, manifest, mapping, output, seed=2026):
    output=Path(output)
    stage5_dir=output/'stage5_full_month'
    # no max_times: process the complete provided file, not the first seven days
    s5=stage5(netcdf,manifest,mapping,stage5_dir,max_times=None)
    inventory(netcdf,output/'native_variable_metadata.json')
    s6=stage6(stage5_dir/'cabauw_observations_enu.csv',
              stage5_dir/'cabauw_observations.metadata.json',
              output/'stage6_full_month',
              stage4_report=stage5_dir/'comparison/stage4_report.json',seed=seed)
    if s5['profiles']!=s6['qa']['timestamp_count']:
        raise ValueError('stage5/stage6 timestamp count mismatch')
    report={'status':'full_month_processing_completed_conditional_on_native_qc',
            'stage5_profiles':s5['profiles'], 'stage6_profiles':s6['qa']['timestamp_count'],
            'stage6_days':s6['qa']['days'],'stage6_figures':len(s6['figures']),
            'source_hash':s5['raw_sha256'],
            'limitations':'native provider quality semantics not independently verified; observational comparison only'}
    (output/'full_month_processing_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--netcdf',required=True,type=Path)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--mapping',type=Path,default=ROOT/'data/examples/knmi_cabauw_tower_profile_mapping.json')
    p.add_argument('--out',type=Path,default=ROOT/'results/atmospheric_testbed/6g_stage6/full_month')
    p.add_argument('--seed',type=int,default=2026)
    a=p.parse_args()
    print(json.dumps(execute(a.netcdf,a.manifest,a.mapping,a.out,a.seed),indent=2))

if __name__=='__main__':main()
