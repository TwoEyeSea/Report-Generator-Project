import React from "react";
import { connect } from "react-redux";
import { createReport } from "../../actions/index";
import ReportForm from "./ReportForm";

class ReportCreate extends React.Component {
  onSubmit = (formValues) => {
    this.props.createReport(formValues);
    // Form values from the ReportForm componenet are passed to the createReport action creator
  };

  render() {
    return (
      <div>
        <h3> Create a Report</h3>
        <ReportForm onSubmit={this.onSubmit} />
      </div>
    );
  }
}

export default connect(null, { createReport })(ReportCreate);
