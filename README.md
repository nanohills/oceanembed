# Step 1. Data collection

- We're collecting the data from `1 Jan 2019` to `31 Dec 2023` (5 years) [daily, multi-year]
- Over the region of North Indian Ocean (5°N to 30°N and 45°E to 105°E)
- For SST, data is around ~`3GB`
- For SSS, data is around ~`0.65GB`
- For SSH, data is around ~`0.16GB`


## To download data

1. SST
```
python download_sst.py --start 2019-01-01 --end 2023-12-31 --outdir ./data/sst 
```

2. SSS
```
python download_sss.py --start 2019-01-01 --end 2023-12-31 --outdir ./data/sss
```

3. SSH
```
python download_ssh.py --start 2019-01-01 --end 2023-12-31 --outdir ./data/ssh
```

4. Winds
```
 python download_winds.py --start 2019-01-01 --end 2023-12-31 --outdir ./data/winds
```

5. Currents
```
python download_currents.py --start 2019-01-01 --end 2023-12-31 --outdir ./data/currents
```

## Regridding


