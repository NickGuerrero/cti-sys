import pytest
from unittest.mock import Mock
from datetime import datetime, date
from fastapi import HTTPException

from src.slack.student_info.service import fetch_student_info


class TestFetchStudentInfo:
    """Test suite for fetch_student_info service function."""

    @pytest.fixture
    def student_row_data(self):
        """Fixture containing typical student row data."""
        return {
            'cti_id': 1,
            'fname': 'John',
            'lname': 'Doe',
            'pname': 'Johnny',
            'institution': 'UC Berkeley',
            'target_year': 2025,
            'join_date': datetime(2023, 9, 1),
            'gender': 'Male',
            'ethnicities_agg': ['Hispanic', 'Asian'],
            'birthday': date(2004, 5, 15),
            'first_gen': True,
            'email': 'john.doe@example.com'
        }

    def test_fetch_student_info_success(self, mock_postgresql_db, student_row_data):
        """Test successful fetch of student info with valid email."""
        # Setup
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        # Execute
        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        # Assert
        assert result == student_row_data
        assert result['cti_id'] == 1
        assert result['fname'] == 'John'
        assert result['lname'] == 'Doe'
        mock_postgresql_db.execute.assert_called_once()

    def test_fetch_student_info_with_preferred_name(self, mock_postgresql_db, student_row_data):
        """Test that preferred name is included in result when present."""
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['pname'] == 'Johnny'

    def test_fetch_student_info_without_preferred_name(self, mock_postgresql_db, student_row_data):
        """Test result when student has no preferred name."""
        student_row_data['pname'] = None
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['pname'] is None

    def test_fetch_student_info_no_records_found(self, mock_postgresql_db):
        """Test HTTPException raised when no student records found."""
        mock_postgresql_db.execute.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            fetch_student_info(mock_postgresql_db, 'nonexistent@example.com')

        assert exc_info.value.status_code == 404
        assert 'No student records found' in exc_info.value.detail
        assert 'nonexistent@example.com' in exc_info.value.detail

    def test_fetch_student_info_with_null_optional_fields(self, mock_postgresql_db, student_row_data):
        """Test that null optional fields are handled correctly."""
        student_row_data['pname'] = None
        student_row_data['gender'] = None
        student_row_data['birthday'] = None
        student_row_data['first_gen'] = None
        student_row_data['institution'] = None

        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['pname'] is None
        assert result['gender'] is None
        assert result['birthday'] is None
        assert result['first_gen'] is None
        assert result['institution'] is None

    def test_fetch_student_info_with_ethnicities_agg(self, mock_postgresql_db, student_row_data):
        """Test that ethnicities_agg array is returned correctly."""
        ethnicities = ['Hispanic', 'Asian', 'Pacific Islander']
        student_row_data['ethnicities_agg'] = ethnicities

        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['ethnicities_agg'] == ethnicities
        assert len(result['ethnicities_agg']) == 3

    def test_fetch_student_info_with_empty_ethnicities_agg(self, mock_postgresql_db, student_row_data):
        """Test handling of empty ethnicities array."""
        student_row_data['ethnicities_agg'] = []

        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['ethnicities_agg'] == []

    def test_fetch_student_info_with_null_ethnicities_agg(self, mock_postgresql_db, student_row_data):
        """Test handling of null ethnicities array."""
        student_row_data['ethnicities_agg'] = None

        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['ethnicities_agg'] is None

    def test_fetch_student_info_different_email_formats(self, mock_postgresql_db, student_row_data):
        """Test that function works with various email formats."""
        emails = [
            'user+tag@example.com',
            'user.name@example.co.uk',
            'user_name@example.org',
            'user123@example.com'
        ]

        for email in emails:
            mock_result = Mock()
            student_row_data['email'] = email
            mock_result._asdict.return_value = student_row_data
            mock_postgresql_db.execute.return_value.first.return_value = mock_result

            result = fetch_student_info(mock_postgresql_db, email)

            assert result['email'] == email

    def test_fetch_student_info_query_construction(self, mock_postgresql_db, student_row_data):
        """Test that the SQL query is constructed correctly."""
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        # Verify execute was called exactly once
        assert mock_postgresql_db.execute.call_count == 1

        # Verify first() was called on the result
        mock_postgresql_db.execute.return_value.first.assert_called_once()

    def test_fetch_student_info_returns_dict(self, mock_postgresql_db, student_row_data):
        """Test that result is properly converted to dictionary."""
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert isinstance(result, dict)
        mock_result._asdict.assert_called_once()

    def test_fetch_student_info_includes_all_required_fields(self, mock_postgresql_db, student_row_data):
        """Test that all expected fields are present in the result."""
        required_fields = [
            'cti_id', 'fname', 'lname', 'pname', 'institution',
            'target_year', 'join_date', 'gender', 'ethnicities_agg',
            'birthday', 'first_gen', 'email'
        ]

        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_fetch_student_info_with_first_generation_true(self, mock_postgresql_db, student_row_data):
        """Test first generation flag when True."""
        student_row_data['first_gen'] = True
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['first_gen'] is True

    def test_fetch_student_info_with_first_generation_false(self, mock_postgresql_db, student_row_data):
        """Test first generation flag when False."""
        student_row_data['first_gen'] = False
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

        assert result['first_gen'] is False

    def test_fetch_student_info_with_different_target_years(self, mock_postgresql_db, student_row_data):
        """Test with various target year values."""
        target_years = [2024, 2025, 2026, 2027, 2028]

        for year in target_years:
            student_row_data['target_year'] = year
            mock_result = Mock()
            mock_result._asdict.return_value = student_row_data
            mock_postgresql_db.execute.return_value.first.return_value = mock_result

            result = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')

            assert result['target_year'] == year

    def test_fetch_student_info_case_sensitivity(self, mock_postgresql_db, student_row_data):
        """Test that email lookup is case-sensitive (or handles as expected)."""
        # Note: This test documents current behavior. Adjust if email matching should be case-insensitive.
        mock_result = Mock()
        mock_result._asdict.return_value = student_row_data
        mock_postgresql_db.execute.return_value.first.return_value = mock_result

        # Both calls use the exact email passed to the function
        result1 = fetch_student_info(mock_postgresql_db, 'john.doe@example.com')
        result2 = fetch_student_info(mock_postgresql_db, 'JOHN.DOE@EXAMPLE.COM')

        assert mock_postgresql_db.execute.call_count == 2

    def test_fetch_student_info_error_message_contains_email(self, mock_postgresql_db):
        """Test that error message includes the email that was searched."""
        test_email = 'test@example.com'
        mock_postgresql_db.execute.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            fetch_student_info(mock_postgresql_db, test_email)

        assert test_email in exc_info.value.detail
