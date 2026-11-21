"""inventory raw knmi netcdf wind and auxiliary variable attributes without guessing flags."""
from pathlib import Path
import argparse
import json


def run(netcdf, output):
    import xarray as xr
    names = ('F','D','PF','MF','SF','SD','z','time','TA','TD','Q','ZMA')
    report = {'status':'raw_netcdf_metadata_inventory_not_quality_screening',
              'file':str(Path(netcdf)), 'variables':{},
              'warning':'auxiliary variables are not interpreted as QC flags without published definitions'}
    with xr.open_dataset(netcdf) as ds:
        for name in names:
            if name not in ds:
                continue
            arr=ds[name]
            report['variables'][name]={
                'dimensions':list(arr.dims), 'shape':list(arr.shape),
                'attrs':{str(k):str(v)[:600] for k,v in arr.attrs.items()},
                'encoding':{str(k):str(v)[:200] for k,v in arr.encoding.items()
                            if k in ('_FillValue','missing_value','dtype','scale_factor','add_offset')},
            }
        report['file_attributes']={str(k):str(v)[:600] for k,v in ds.attrs.items()}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--netcdf',type=Path,required=True)
    p.add_argument('--out',type=Path,default=Path('results/atmospheric_testbed/6g_stage6/knmi_native_metadata.json'))
    a=p.parse_args();r=run(a.netcdf,a.out)
    print(json.dumps({'status':r['status'],'variables':list(r['variables']),
                      'output':str(a.out)},indent=2))

if __name__=='__main__':main()
