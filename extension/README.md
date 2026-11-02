# JobPilot Apply Assist (Chrome extension)

Fills job application forms from your JobPilot details and saved answers. It never submits:
you review every field and click Submit yourself.

## Install (once)
1. Start the JobPilot backend (`http://127.0.0.1:8000`).
2. Chrome → `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → pick this
   `extension` folder.
3. Pin "JobPilot Apply Assist" to the toolbar.
4. In the JobPilot web app, open **Apply profile** and fill in your details.

## Use
1. Open a job's application form (log in first if the site needs it, e.g. Workday).
2. Click the extension → **Fill this form**. The first time, Chrome asks for access to sites;
   this is needed because many forms sit in an embedded frame from another domain.
3. Fields are outlined: green = from your profile or an exact saved answer, amber = a guess or
   an AI draft (check it), red = nothing known.
4. Fix anything, then click **Save my answers** so the next form fills them.
5. Submit on the site, then click **Mark applied** to move the job to Applied in the tracker.

Workday: run **Fill** again on each step of the form.
LinkedIn and Naukri are off by default (their terms ban automation); tick "Enabled on this
site" to turn one on at your own risk.
Keep the popup open while it fills; AI drafts can take up to a minute with the local model.

The CV uploaded is `[apply] cv_path` in `jobpilot-backend/settings.toml`.
