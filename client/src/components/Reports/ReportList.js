import React from "react";
import { connect } from "react-redux";
import { fetchReports } from "../../actions";
import { Link } from "react-router-dom";

class ReportList extends React.Component {
  componentDidMount() {
    this.props.fetchReports();
    // retrieves all the required data for the reports into our state on mounting the component
  }

  renderAdmin = (report) => {
    if (!report.userId) {
      return;
    } else if (report.userId === this.props.currentUserId) {
      return (
        <div className="right floated content">
          <Link
            className="ui button primary"
            to={`/reports/edit/${report._id}`}
          >
            Edit
          </Link>
          <Link className="ui button red" to={`/reports/delete/${report._id}`}>
            Delete
          </Link>
        </div>
      );
    }
    return;
  };

  // Helper function to render data from the db.js file into jsx elements for the reportList component
  // * NB * If the db.json file isn't structured properly the renderList() helper function will not render the list properly.
  // It is important to test that the CreateReport() commponent is posting the db.json elements properly. You may have to delete previous elements if they corrupt the db.json file.
  renderList() {
    return this.props.reports.map((report) => {
      // This if statement is currently being used to exclude the res.json message from being displayed within the list of reports. the res.json message is requrired to complete
      if (!report.msg) {
        return (
          <div className="item" key={report._id}>
            {this.renderAdmin(report)}
            <i className="large middle aligned icon file alternate outline" />
            <div className="content">
              <Link to={`/reports/show/${report._id}`}>
                {" "}
                {/*link will eventually lead to ReportShow component*/}
                {/*How to display nested array data */}
                {/* {report.trialPits.map((r) => r.groundWaterLevel)}{" "} */}
                AMR:{report.reportId} | Client: {report.clientName}
                <div className="description">
                  BLOCK: {report.block} PARCEL(S) {report.parcel},{" "}
                  {report.siteAddress.toUpperCase()}
                </div>
              </Link>
            </div>
          </div>
        );
      }
    });
  }

  // Helper function to render the "Create New Report" button
  renderCreate = () => {
    if (this.props.isSignedIn) {
      return (
        <div style={{ textAlign: "right" }}>
          <Link to="/reports/new" className="ui button primary">
            Create New Report
          </Link>
        </div>
      );
    }
  };

  render() {
    return (
      <div>
        <h2>Reports</h2>
        <div className="ui relaxed divided list">{this.renderList()}</div>
        {/* the renderList helper function renders the jsx items into the celled list div */}
        {this.renderCreate()}
      </div>
    );
  }
}

const mapStateToProps = (state) => {
  return {
    reports: Object.values(state.reports),
    currentUserId: state.auth.userId,
    isSignedIn: state.auth.isSignedIn,
  };
};

export default connect(mapStateToProps, { fetchReports })(ReportList);
