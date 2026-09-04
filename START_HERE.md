# Put Humble Seed on GitHub

Suggested repository name: **humble-seed**

Suggested description:

> Raised, Not Rented research prototype: owner-authorized state changes, signed checkpoints, external witnesses, and adversarial probes.

## Upload through GitHub

1. Extract `humble-seed-github.zip` and open the `humble-seed` folder.
2. [Create a GitHub repository](https://github.com/new) named `humble-seed`.
   Choose your desired visibility. Leave the generated README, license, and
   `.gitignore` options off; the package includes its own files.
3. Use **uploading an existing file**, or **Add file → Upload files**.
4. Upload the **contents** of the extracted folder, preserving subdirectories.
   Include `.github`, `.gitignore`, and `.gitattributes`. `README.md` belongs
   at the repository root. Upload the extracted files, not just the ZIP.
5. Commit the upload, then check the **Actions** tab for the validation run.

GitHub documents the interface in
[Adding a file to a repository](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

## Upload with Git

Create the empty GitHub repository, then run these commands from the extracted
`humble-seed` directory. Replace `YOUR-USERNAME` with your GitHub account or
organization name.

```bash
git init -b main
git add .
git commit -m "Package Humble Seed research snapshots and validation"
git remote add origin https://github.com/YOUR-USERNAME/humble-seed.git
git push -u origin main
```

Use your normal GitHub authentication and Git author settings. The ZIP contains
the source tree; Git metadata and generated organism state are excluded.
See GitHub's
[local repository upload guide](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

## First commands after installation

```bash
python -m pip install -r requirements.txt
python run.py example
python run.py validate
python -m unittest discover -s tests -v
```

All ten uploads are preserved. The default v0.6 matches the supplied assertion
suite; the other v0.6 remains separately runnable. See
[the version map](docs/VERSIONS.md) before combining files or changing imports.

The original files did not specify a reuse license. The package records that
decision as open in [LICENSE_STATUS.md](LICENSE_STATUS.md).
