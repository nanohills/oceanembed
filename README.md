# Step 1. Data collection

- We're collecting the data from `1 Jan 2019` to `31 Dec 2023` (5 years) [daily, multi-year]
- Over the region of North Indian Ocean (5°N to 30°N and 45°E to 105°E)
- For SST, data is around ~`3GB`
- For SSS, data is around ~`0.65GB`
- For SSH, data is around ~`0.16GB`


# claude's plan

## Phase 1: Data Acquisition

1. **Download all 5 surface input variables** for the full North Indian Ocean box (5-30N, 45-105E), daily, for your chosen year range: SST (done), SSS, SSH/SLA, currents (U,V), winds (U,V)
2. **Download the target variable**: GLORYS reanalysis temperature at all 15 depth levels, same domain, same date range
3. **Download the independent validation set**: Gridded ARGO from INCOIS LAS, kept completely separate, used only for final evaluation, never for training

## Phase 2: Preprocessing

4. **Regrid everything to a common 0.25°×0.25° daily grid.** Each input arrives at a different native resolution (SST is 0.05°, SSS is 0.125°, etc.), this step forces them all onto identical grid cells so they can be stacked as channels
5. **Build/confirm the land-ocean mask** (you now know OSTIA ships one in the `mask` variable, reuse it rather than building from scratch)
6. **Stack into training tensors**: input shape `(time, 7 channels, lat, lon)`, target shape `(time, 15 depth channels, lat, lon)`
7. **Split by time**, not randomly: e.g. train on one block of years, validate on a later block, test on the most recent block, to avoid the model "peeking" at the future

## Phase 3: Baseline Model

8. **Build the Stage 1 U-Net**: input the 7-channel surface stack, output the 15-channel depth stack, single day at a time
9. **Train it**, patch-based (64×64 tiles) to fit your 6GB VRAM
10. **Get first numbers**: RMSE and correlation per depth level against your held-out GLORYS test split

## Phase 4: Embedding Upgrade (the actual "OceanEmbed" part)

11. **Pretrain an autoencoder** on the surface variables alone (self-supervised, no labels needed): compress to a latent embedding, reconstruct the same surface fields back
12. **Attach a new decoder head** to that trained encoder, fine-tune it to map the latent embedding to the 15-depth temperature profile instead

## Phase 5: Validation

13. **Evaluate against ARGO** (the real, independent measurements), separately from your GLORYS-based test metrics, report RMSE/correlation/bias per depth level for both
14. **Error analysis**: where does the model do worst? Usually deeper levels, or coastal/upwelling zones, worth understanding and being able to explain to judges

## Phase 6: Demo & Submission

15. **Build the PoC visualization**, zoomed into Bay of Bengal or Arabian Sea as the PS explicitly calls for, even though training covered the full domain
    Here's the breakdown, in the order you'd actually execute them.

## Phase 1: Data Acquisition (you're partway here already)

1. **Download all 5 surface input variables** for the full North Indian Ocean box (5-30N, 45-105E), daily, for your chosen year range: SST (done), SSS, SSH/SLA, currents (U,V), winds (U,V)
2. **Download the target variable**: GLORYS reanalysis temperature at all 15 depth levels, same domain, same date range
3. **Download the independent validation set**: Gridded ARGO from INCOIS LAS, kept completely separate, used only for final evaluation, never for training

## Phase 2: Preprocessing

4. **Regrid everything to a common 0.25°×0.25° daily grid.** Each input arrives at a different native resolution (SST is 0.05°, SSS is 0.125°, etc.), this step forces them all onto identical grid cells so they can be stacked as channels
5. **Build/confirm the land-ocean mask** (you now know OSTIA ships one in the `mask` variable, reuse it rather than building from scratch)
6. **Stack into training tensors**: input shape `(time, 7 channels, lat, lon)`, target shape `(time, 15 depth channels, lat, lon)`
7. **Split by time**, not randomly: e.g. train on one block of years, validate on a later block, test on the most recent block, to avoid the model "peeking" at the future

## Phase 3: Baseline Model

8. **Build the Stage 1 U-Net**: input the 7-channel surface stack, output the 15-channel depth stack, single day at a time
9. **Train it**, patch-based (64×64 tiles) to fit your 6GB VRAM
10. **Get first numbers**: RMSE and correlation per depth level against your held-out GLORYS test split

## Phase 4: Embedding Upgrade (the actual "OceanEmbed" part)

11. **Pretrain an autoencoder** on the surface variables alone (self-supervised, no labels needed): compress to a latent embedding, reconstruct the same surface fields back
12. **Attach a new decoder head** to that trained encoder, fine-tune it to map the latent embedding to the 15-depth temperature profile instead

## Phase 5: Validation

13. **Evaluate against ARGO** (the real, independent measurements), separately from your GLORYS-based test metrics, report RMSE/correlation/bias per depth level for both
14. **Error analysis**: where does the model do worst? Usually deeper levels, or coastal/upwelling zones, worth understanding and being able to explain to judges

## Phase 6: Demo & Submission

15. **Build the PoC visualization**, zoomed into Bay of Bengal or Arabian Sea as the PS explicitly calls for, even though training covered the full domain
16. **Package the pitch**: PPT, problem framing, architecture diagram, results, and a live or recorded demo
