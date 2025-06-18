import pytest
from unittest.mock import MagicMock

from src.database.postgres.models import Student, Accelerate, AccountabilityGroup
from src.students.accelerate.assign_sa.service import assign_student_SA

class TestAssignSA:
    # =========================
    # Successful Assignments
    # =========================

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_assign_sa_success(self, env, monkeypatch, mock_postgresql_db):
        """Test successful assignment of SA to a student with no existing SA."""
        # monkeypatch.setattr(settings, "app_env", env)
        
        # Mock data
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        accelerate_record = Accelerate(cti_id=1, active=True)
        sa_group_1 = AccountabilityGroup(ag_id=1, group_name="Group A", student_accelerator="SA1")
        sa_group_2 = AccountabilityGroup(ag_id=2, group_name="Group B", student_accelerator="SA2")
        
        # Setup relationships
        student.accelerate_record = accelerate_record
        accelerate_record.accountability_group = None
        accelerate_record.ag_record = None
        
        # Mock query behaviors
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student,  # First call: get student
            sa_group_1  # Second call: get SA group
        ]
        
        # Mock the SA counts query
        mock_postgresql_db.query.return_value.outerjoin.return_value.group_by.return_value.all.return_value = [
            ("SA1", 5),
            ("SA2", 3)
        ]
        
        # Call the function
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False
        )
        
        # Verify result
        assert result["status"] == 200
        assert result["assigned_sa"] == "SA2"  # SA2 has fewer students
        assert "group_name" in result
        assert result["ag_id"] in [1, 2]
        
        # Verify database operations
        mock_postgresql_db.commit.assert_called_once()

    def test_student_not_found(self, mock_postgresql_db):
        """Test when student ID doesn't exist."""
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = None
        
        result = assign_student_SA(
            student_id=999,
            db=mock_postgresql_db,
            overwrite=False
        )
        
        assert result["status"] == 404
        assert "Student with ID 999 not found" in result["message"]
        mock_postgresql_db.commit.assert_not_called()
    
    def test_student_not_in_accelerate(self, mock_postgresql_db):
        """Test when student exists but isn't in Accelerate program."""
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        # No accelerate_record relation
        
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = student
        
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False
        )
        
        assert result["status"] == 400
        assert "Student is not part of the Accelerate program" in result["message"]
        mock_postgresql_db.commit.assert_not_called()
    
    def test_already_has_sa_no_overwrite(self, mock_postgresql_db):
        """Test when student already has an SA and overwrite is False."""
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        accelerate_record = Accelerate(cti_id=1, active=True, accountability_group=1)
        ag_record = AccountabilityGroup(ag_id=1, group_name="Group A", student_accelerator="SA1")
        
        # Create proper relationship chain
        accelerate_record.ag_record = ag_record
        student.accelerate_record = accelerate_record
        
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = student
        
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False
        )
        
        assert result["status"] == 400
        assert "Student already has an assigned SA" in result["message"]
        mock_postgresql_db.commit.assert_not_called()
    
    def test_specific_sa_assignment(self, mock_postgresql_db):
        """Test when a specific SA is requested."""
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        accelerate_record = Accelerate(cti_id=1, active=True)
        sa_group = AccountabilityGroup(ag_id=1, group_name="Group A", student_accelerator="TargetSA")
        
        student.accelerate_record = accelerate_record
        
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student,  # First call: get student
            sa_group  # Second call: get specific SA group
        ]
        
        # Mock the SA counts query
        mock_postgresql_db.query.return_value.outerjoin.return_value.group_by.return_value.all.return_value = [
            ("TargetSA", 5),
            ("OtherSA", 3)
        ]
        
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False,
            sa="TargetSA"  # Request specific SA
        )
        
        assert result["status"] == 200
        assert result["assigned_sa"] == "TargetSA"
        assert result["group_name"] == "Group A"
        mock_postgresql_db.commit.assert_called_once()
    
    def test_exclude_list(self, mock_postgresql_db):
        """Test assignment when SAs are excluded from consideration."""
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        accelerate_record = Accelerate(cti_id=1, active=True)
        sa_group = AccountabilityGroup(ag_id=2, group_name="Group B", student_accelerator="SA2")
        
        student.accelerate_record = accelerate_record
        
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student,  # First call: get student
            sa_group  # Second call: get SA group (SA2)
        ]
        
        # Mock the SA counts query
        mock_postgresql_db.query.return_value.outerjoin.return_value.group_by.return_value.all.return_value = [
            ("SA1", 3),  # SA1 has fewer students but is excluded
            ("SA2", 5),
            ("SA3", 4)
        ]
        
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False,
            exclude_list=["SA1", "SA3"]  # Exclude SA1 and SA3
        )
        
        assert result["status"] == 200
        assert result["assigned_sa"] == "SA2"  # SA2 is the only choice
        mock_postgresql_db.commit.assert_called_once()
    
    def test_no_available_sas(self, mock_postgresql_db):
        """Test when no SAs are available."""
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        accelerate_record = Accelerate(cti_id=1, active=True)
        
        student.accelerate_record = accelerate_record
        
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = student
        
        # Mock the SA counts query to return empty list
        mock_postgresql_db.query.return_value.outerjoin.return_value.group_by.return_value.all.return_value = []
        
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False
        )
        
        assert result["status"] == 404
        assert "No Student Accelerators found" in result["message"]
        mock_postgresql_db.commit.assert_not_called()
    
    def test_database_error(self, mock_postgresql_db):
        """Test handling database errors during commit."""
        student = Student(cti_id=1, fname="Jane", lname="Doe", target_year=2025)
        accelerate_record = Accelerate(cti_id=1, active=True)
        sa_group = AccountabilityGroup(ag_id=1, group_name="Group A", student_accelerator="SA1")
        
        student.accelerate_record = accelerate_record
        
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student,
            sa_group
        ]
        
        # Mock the SA counts query
        mock_postgresql_db.query.return_value.outerjoin.return_value.group_by.return_value.all.return_value = [
            ("SA1", 5)
        ]
        
        # Simulate database error on commit
        mock_postgresql_db.commit.side_effect = Exception("Database error")
        
        result = assign_student_SA(
            student_id=1,
            db=mock_postgresql_db,
            overwrite=False
        )
        
        assert result["status"] == 500
        assert "Database error occurred" in result["message"]
        mock_postgresql_db.rollback.assert_called_once()