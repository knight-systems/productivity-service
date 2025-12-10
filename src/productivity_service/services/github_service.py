"""GitHub API service for Obsidian vault operations."""

import json
import logging
from base64 import b64decode, b64encode
from functools import lru_cache

import boto3
from github import Github, GithubException

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_github_token(secret_arn: str) -> str:
    """Retrieve GitHub PAT from AWS Secrets Manager (cached)."""
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])
    return secret["token"]


class GitHubService:
    """Service for interacting with GitHub repository via API."""

    def __init__(self, repo_name: str, branch: str, secret_arn: str):
        """Initialize GitHub service.

        Args:
            repo_name: Repository in format "owner/repo"
            branch: Branch name (e.g., "main")
            secret_arn: AWS Secrets Manager ARN for GitHub PAT
        """
        self.repo_name = repo_name
        self.branch = branch
        self._secret_arn = secret_arn
        self._github: Github | None = None
        self._repo = None

    @property
    def github(self) -> Github:
        """Lazy-load GitHub client."""
        if self._github is None:
            token = _get_github_token(self._secret_arn)
            self._github = Github(token)
        return self._github

    @property
    def repo(self):
        """Lazy-load repository object."""
        if self._repo is None:
            self._repo = self.github.get_repo(self.repo_name)
        return self._repo

    def get_file_content(self, path: str) -> tuple[str, str] | None:
        """Get file content and SHA from repository.

        Args:
            path: File path relative to repository root

        Returns:
            Tuple of (content, sha) or None if file doesn't exist
        """
        try:
            contents = self.repo.get_contents(path, ref=self.branch)
            if isinstance(contents, list):
                # Path is a directory
                return None
            content = b64decode(contents.content).decode("utf-8")
            return content, contents.sha
        except GithubException as e:
            if e.status == 404:
                return None
            logger.error(f"Error getting file {path}: {e}")
            raise

    def update_file(
        self,
        path: str,
        content: str,
        message: str,
        sha: str | None = None,
    ) -> str:
        """Update or create a file in the repository.

        Args:
            path: File path relative to repository root
            content: New file content
            message: Commit message
            sha: File SHA (required for updates, None for creates)

        Returns:
            New commit SHA
        """
        encoded_content = b64encode(content.encode("utf-8")).decode("utf-8")

        try:
            if sha:
                # Update existing file
                result = self.repo.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=sha,
                    branch=self.branch,
                )
            else:
                # Create new file
                result = self.repo.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=self.branch,
                )

            return result["commit"].sha
        except GithubException as e:
            logger.error(f"Error updating file {path}: {e}")
            raise

    def append_to_file(
        self,
        path: str,
        content_to_append: str,
        message: str,
    ) -> str:
        """Append content to an existing file or create it.

        Args:
            path: File path relative to repository root
            content_to_append: Content to append
            message: Commit message

        Returns:
            New commit SHA
        """
        existing = self.get_file_content(path)

        if existing:
            current_content, sha = existing
            new_content = current_content + content_to_append
            return self.update_file(path, new_content, message, sha)
        else:
            return self.update_file(path, content_to_append, message, None)

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in the repository."""
        return self.get_file_content(path) is not None

    def list_folder_files(self, folder_path: str) -> list[str]:
        """List all files in a folder.

        Args:
            folder_path: Folder path relative to repository root

        Returns:
            List of file paths (including folder prefix)
        """
        try:
            contents = self.repo.get_contents(folder_path, ref=self.branch)
            if not isinstance(contents, list):
                return []
            return [item.path for item in contents if item.type == "file"]
        except GithubException as e:
            if e.status == 404:
                return []
            logger.error(f"Error listing folder {folder_path}: {e}")
            raise
