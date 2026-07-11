# Contributing

This repository contains a ROS 1 catkin workspace under `edge/`. Keep changes scoped to the package or launch path they affect, and avoid committing generated runtime output.

## Workflow

1. Create a feature branch from `main`.
2. Keep credentials in environment variables or local `.env` files. Do not commit real API keys, NTRIP credentials, SSH keys, rosbag captures, build outputs, or machine-specific paths.
3. Build before opening a pull request:

```bash
cd edge
catkin_make
```

4. Run package-level scripts or launch-file smoke tests relevant to the changed module.
5. Open a pull request using the template and include changed ROS topics, launch files, parameters, and hardware assumptions.

## Repository Hygiene

- Generated folders such as `build/`, `devel/`, `install/`, and `log/` must stay untracked.
- Large model artifacts should use Git LFS when they need to be versioned.
- Shared configuration examples belong in committed example files. Local secrets belong in `.env`, shell exports, or deployment tooling.
- New ROS packages under `edge/src/NVI/` should include `package.xml`, `CMakeLists.txt`, launch/config documentation, and a short README when the behavior is not obvious from the package name.
