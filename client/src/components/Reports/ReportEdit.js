import React from "react";
import { connect } from "react-redux";
import { fetchReport, editReport } from "../../actions/index";
import ReportForm from "./ReportForm";
import _ from "lodash";
//importing the fetchReport action creator because this application is making use of URL Navigation
// This ReportEdit component needs to have access to the data by itself to be function (even in the event of the user loading this component first)
// Otherwise users will always need to load the ReportList component first to fetch the required data.
// Now the ReportEdit Component will fetchn the required data necessary to edit this Report via componentDidMount.

class ReportEdit extends React.Component {
  componentDidMount() {
    this.props.fetchReport(this.props.match.params.id);
  }

  onSubmit = (formValues) => {
    this.props.editReport(this.props.match.params.id, formValues);
  };

  render() {
    if (!this.props.report) {
      return <div>Loading...</div>;
    }

    return (
      <div>
        <h3>Edit Report</h3>
        <ReportForm
          onSubmit={this.onSubmit}
          initialValues={_.pick(
            this.props.report,
            "userId",
            "reportId",
            "clientName",
            "block",
            "parcel",
            "siteAddress",
            "investigationDate",
            "engineerAMR",
            "weather",
            "investigationDuration",
            "trialPitNumber",
            "unitDescriptions",
            "trialPits"
          )}
        />
      </div>
    );
  }
}

const mapStateToProps = (state, ownProps) => {
  return {
    report: state.reports[ownProps.match.params.id],
  };
};

export default connect(mapStateToProps, { fetchReport, editReport })(
  ReportEdit
);
