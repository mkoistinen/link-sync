from http import HTTPStatus
from pathlib import Path

from requests import Session
from requests.auth import HTTPDigestAuth


DATA = Path(__file__).parent.joinpath('data')


def test_auth(api):
    """Test that PrusaLinkApi.auth works as expected."""
    assert isinstance(api.auth, HTTPDigestAuth)


def test_session(api):
    """Test that PrusaLinkApi.session works as expected."""
    assert isinstance(api.session, Session)


def test_status_response_ok(mocker, api, mock_status_response):
    """Test that PrusaLink.status_response() works as expected."""
    mock_status_response.status_code = HTTPStatus.OK
    mocker.patch('requests.Session.request', return_value=mock_status_response)
    assert 'storage' in api.status_response().payload


def test_status_response_not_ok(mocker, api, mock_status_response):
    """Test that PrusaLink.status_response() works as expected."""
    mock_status_response.status_code = HTTPStatus.BAD_GATEWAY
    mocker.patch('requests.Session.request', return_value=mock_status_response)
    assert api.status_response().status_code == HTTPStatus.BAD_GATEWAY


def test_files_response_get_file_ok(mocker, api, mock_files_response):
    """Test that PrusaLink.status_response() works as expected."""
    mock_files_response.status_code = HTTPStatus.OK
    mocker.patch('requests.Session.request', return_value=mock_files_response)
    assert 'children' in api.files_response(path='usb').payload


def test_files_response_get_file_headers_ok(mocker, api, mock_files_response):
    """Test that PrusaLink.status_response() works as expected."""
    mock_files_response.status_code = HTTPStatus.OK
    mocker.patch('requests.Session.request', return_value=mock_files_response)

    assert 'children' in api.files_response(
        path='usb', headers={'X-Api-Key': 'banana'}).payload


def test_files_response_put_file_ok(mocker, api, mock_files_put_response):
    """Test that PrusaLink.status_response() works as expected."""
    mock_files_put_response.status_code = HTTPStatus.OK
    mocker.patch('requests.Session.request',
                 return_value=mock_files_put_response)
    with open(DATA.joinpath('file_hierarchy', 'other.gcode')) as fp:
        payload = api.files_response(method='PUT', path='usb', data=fp)
        assert payload
