#!/bin/bash

# A simple script to stage, commit, and push changes to a Git repository.

# --- Configuration ---
# The file to be added to the commit.
FILENAME="index.html"

# Default commit message if none is provided.
DEFAULT_COMMIT_MESSAGE="feat: Update landing page via AI Agent workflow"

# --- Script Logic ---

# Exit immediately if a command exits with a non-zero status.
set -e

# Check if we are in a git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "❌ Error: Not a git repository. Aborting."
    exit 1
fi

# Check if the file exists
if [ ! -f "$FILENAME" ]; then
    echo "❌ Error: File '$FILENAME' not found. Aborting."
    exit 1
fi

# Use the first argument as the commit message, or use the default.
COMMIT_MESSAGE="${1:-$DEFAULT_COMMIT_MESSAGE}"

echo "🚀 Starting Git deployment..."

# 1. Stage the file
echo "   - Staging '$FILENAME'..."
git add "$FILENAME"

# 2. Commit the changes
echo "   - Committing with message: \"$COMMIT_MESSAGE\""
git commit -m "$COMMIT_MESSAGE"

# 3. Push to the remote repository (assumes 'origin' and the current branch are set up)
echo "   - Pushing to remote..."
git push

echo "✅ Success! Changes have been pushed to the repository."
