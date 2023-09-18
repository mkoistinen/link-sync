from datetime import datetime
from functools import cached_property
import logging
from pathlib import Path
from typing import Generator, Optional, Set, Union

from .apis import ApiException, PrusaLinkApi


logger = logging.getLogger(__name__)


class StorageException(Exception):
    """An exception for storage API related issues."""


class FileNode:
    """
    Describes a remote file.

    Parameters
    ----------
    name : str
        The 8.3 "short" name of the file or folder.
    type : str
        The file type. The important ones are "PRINT_FILE" and "FOLDER".
    ro : bool
        If True, the file is set to be read only.
    m_timestamp : int or None, default None
        Optional. The integer seconds since the Epoch that the file was
        last modified.
    display_name : str or None, default None
        Optional. The display name of the file or folder.
    parent_node : FileNode or None
        Optional. The parent FileNode instance to this file or folder.
    kwargs : Mapping
        Any other keyword arguments passed.
    """

    def __init__(
        self,
        *,
        name: str,
        type: str,
        ro: bool,
        m_timestamp: Optional[int] = None,
        display_name: Optional[str] = None,
        parent_node: Optional["FileNode"] = None,
        **kwargs,
    ):
        self.name = name  # 8.3 "short" name
        self.ro = ro
        self.type = type
        self.m_timestamp = m_timestamp
        self.display_name = display_name

        self._kwargs = kwargs
        self._short_name: Optional[str] = None

        self.child_nodes: Set = set()
        self.parent_node = parent_node

    def __str__(self) -> str:
        """Return a human-consumable instance representation."""
        return f'File: "{self.display_name or self.name}"'

    def __repr__(self) -> str:
        """Return a instance representation."""
        return f"<{self.__str__()}>"

    @cached_property
    def is_dir(self):
        """Return True if this node is a FOLDER."""
        return self.type == "FOLDER"

    @cached_property
    def full_short_path(self):
        """Return the path composed of 8.3 "short" components."""
        if self.parent_node:
            return f"{self.parent_node.full_short_path}/{self.name}"
        else:
            return f"/{self.name}"

    @cached_property
    def full_display_path(self):
        """Return the full display path of the node."""
        if self.parent_node:
            return (
                f"{self.parent_node.full_display_path}/"
                f"{self.display_name or self.name}"
            )
        else:
            # Root nodes may not have display_names.
            return f"/{self.display_name or self.name}"

    @cached_property
    def m_datetime(self) -> Union[datetime, None]:
        """Return the modificiation date of the file as a datetime."""
        if self.m_timestamp:
            return datetime.utcfromtimestamp(self.m_timestamp)
        else:
            return None


class Storage:
    """
    Represents a storage facility for a printer.

    The storage class creates and manages a subclass of AbstractApi as well as
    a local "cache" of the filesystem hierarchy as a network of FileNodes.

    Parameters
    ----------
    name : str
        The common name of the host (3D Printer device).
    host : str
        The host (including the protocol) to use when using the API.
        Example: 'http://192.168.0.1'.
    username : str
        The username to use when using the API.
    password : str
        The password to use when using the API
    """

    def __init__(self, name: str, host: str, username: str, password: str):
        self.name = name
        self.api_key = password
        self.api = PrusaLinkApi(
            name=self.name, host=host, username=username, password=password
        )
        self.root_node = self._get_root_node()
        self._build_storage(self.root_node)

    def __str__(self) -> str:
        """Return a human-readable instance representation."""
        try:
            name = self.root_node.display_name or self.root_node.name
            return f"Storage: {self.name}:{name}"
        except Exception:
            return f"Storage: {self.name}:UNDEFINED"

    def __repr__(self) -> str:
        """Return a instance representation."""
        return f"<{self.__str__()}>"

    def _get_root_node(self) -> FileNode:
        """
        Fetch the given printer's storage path root FileNode.

        All other FileNodes representing files on this printer will ultimately
        parent this FileNode instance in a tree-like fashion representing the
        whole filesystem.

        Raises
        ------
        StorageException
            If the API cannot return a root node, this exception is raised.
        """
        # The printer's status also returns the storage root.
        status_response = self.api.status_response()
        if isinstance(status_response.payload, dict):
            storage_path = status_response.payload["storage"]["path"]
            files_response = self.api.files_response(path=storage_path)
            if isinstance(files_response.payload, dict):
                return FileNode(**files_response.payload, parent_node=None)

        raise StorageException(f"Could not get the root path for {self}")

    def reload(self):
        """Rebuilds the storage node network."""
        self.root_node.child_nodes = set()
        self._build_storage(self.root_node)

    def _build_storage(self, file_obj: FileNode):
        """
        Given a FileNode, recursively build a storage tree.

        This is a recursive method which ultimately constructs a tree of
        FileNodes from the remote device together as a network.

        Parameters
        ----------
        file_obj : FileNode
            The FileNode currently being traversed.
        """
        short_path = file_obj.full_short_path
        response = self.api.files_response(path=short_path)

        # If it has children, recurse...
        if response.success and isinstance(response.payload, dict):
            for child_map in response.payload.get("children", []):
                child_obj = FileNode(**child_map, parent_node=file_obj)
                file_obj.child_nodes.add(child_obj)
                if child_obj.type == "FOLDER":
                    self._build_storage(file_obj=child_obj)

    def gen_nodes(
        self, file_node: Optional[FileNode] = None
    ) -> Generator[FileNode, None, None]:
        """
        Yield all FileNode instances.

        This works by starting from the `root_obj` and recursively traversing
        any nodes' `child_objs` sets.

        Parameters
        ----------
        file_obj : FileNode or None, default None
            Optional. FileNode to start with. If not provided, this method
            will start with the `root_obj`.

        Yields
        ------
        FileNode
        """
        if file_node is None:
            file_node = self.root_node

        yield file_node

        for child_node in file_node.child_nodes:
            yield from self.gen_nodes(child_node)

    def get_node_for_display_path(
        self, path: Union[Path, str]
    ) -> Union[FileNode, None]:
        """
        Given a `path`, return the FileNode representing it, if any.

        Parameters
        ----------
        path : Path or str
            A Path, relative to the `root_obj`. This path is based on the
            "display_names" of the path components, not the 8.3 variants.

        Returns
        -------
        FileNode or None
            If an object is found that represents the given path, it is
            returned, otherwise `None` is returned.
        """
        if isinstance(path, Path):
            path = str(path)
        for file_node in self.gen_nodes():
            if file_node.full_display_path == path:
                return file_node
        return None

    def get_node_for_short_path(
        self, path: Union[Path, str]
    ) -> Union[FileNode, None]:
        """
        Given a `path`, return the FileNode representing it, if any.

        Parameters
        ----------
        path : Path or str
            A Path, relative to the `root_obj`. This path is based on the
            "name" or 8.3 version of the path components.

        Returns
        -------
        FileNode or None
            If an object is found that represents the given path, it is
            returned, otherwise `None` is returned.
        """
        if isinstance(path, Path):
            path = str(path)
        for file_node in self.gen_nodes():
            if file_node.full_short_path == path:
                return file_node
        return None

    def get_shorter_path(self, remote_path: Union[Path, str]) -> Path:
        """
        Shorten the given remote_path using as many 8.3 components as possible.

        Parameters
        ----------
        remote_path : Path or str
            The path to shorten.

        Returns
        -------
        Path
            The shortened-est path to the FileNode referenced by `remote_path`.
        """
        if not isinstance(remote_path, Path):
            remote_path = Path(remote_path)

        for parent in remote_path.parents:
            for node in self.gen_nodes():
                if node.full_display_path == str(parent):
                    return Path(node.full_short_path).joinpath(
                        remote_path.relative_to(parent)
                    )

        # Looks like this is a completely new path...
        return remote_path

    def create_remote_folder(self, remote_path: Union[Path, str]):
        """
        Create the given `remote_path` if ncessary. Return the final node.

        Shorten the path as much as possible, then request that the path is
        created using a PUT and setting the `Create-Folder` header.

        Parameters
        ----------
        remote_path : Path or str
            The folder to create.
        """
        if not isinstance(remote_path, Path):
            remote_path = Path(remote_path)

        if self.get_node_for_display_path(remote_path):
            return True

        path = self.get_shorter_path(remote_path)
        headers = {"Create-Folder": "true"}
        try:
            self.api.files_response(method="PUT", path=path, headers=headers)
        except ApiException as e:
            logger.error(str(e))
            return False
        except Exception:
            logger.error(
                f'Unable to create a new folder "{remote_path}" on printer.'
            )
            return False
        else:
            return True

    def upload_file(
        self, local_path: Union[Path, str], remote_path: Union[Path, str]
    ) -> bool:
        """
        Upload a new file into storage from `local_path`.

        Parameters
        ----------
        local_path : Path or str
            The path to the local file to upload.
        remote_path : Path or str
            The remote_path where the uploaded file should go.

        Returns
        -------
        bool
            True if the upload is successful.
        """
        if not isinstance(local_path, Path):
            local_path = Path(local_path)
        if not isinstance(remote_path, Path):
            remote_path = Path(remote_path)

        shorter_path = self.get_shorter_path(remote_path)
        if shorter_path.suffix:
            parent_path = shorter_path.parent
        else:
            parent_path = shorter_path

        # If the parent folder doesn't exist, create it first.
        if not self.get_node_for_short_path(parent_path):
            try:
                self.create_remote_folder(parent_path)
            except ApiException as e:
                logger.error(str(e))
            except Exception:
                logger.error("Folder already exists?")

        headers = {
            "Overwrite": "true",
            "Print-After-Upload": "false",
            "X-Api-Key": self.api_key,
        }
        if local_path.suffix == ".gcode":
            headers.update({"Content-type": "text/x.gcode"})
        elif local_path.suffix == ".bbf":
            headers.update({"Content-type": "application/octet-stream"})
        try:
            with open(local_path, mode="rb") as source_fp:
                self.api.files_response(
                    "PUT", path=shorter_path, data=source_fp, headers=headers
                )
        except ApiException as e:
            logger.error(str(e))
            return False
        except Exception:
            logger.error(
                f'Unable to upload file "{local_path}" to '
                f'"{remote_path}" on printer.'
            )
            return False
        else:
            return True

    def delete_file(self, node: FileNode) -> bool:
        """
        Delete the file represented by the given `node` from the printer.

        Parameters
        ----------
        node : FileNode
            The node that represents the remote_file to delete.

        Returns
        -------
        bool
            True if the deletion was successful.
        """
        headers = {"X-Api-Key": self.api_key}
        try:
            self.api.files_response(
                "DELETE", path=node.full_short_path, headers=headers
            )
        except Exception:
            logger.exception(
                f"Could not delete file " f'"{node.full_display_path}".'
            )
            return False
        else:
            return True
