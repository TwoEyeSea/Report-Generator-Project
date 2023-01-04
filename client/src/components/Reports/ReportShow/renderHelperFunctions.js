import React from "react";

// Helper function to render unit descriptions as DOM elements
export const renderUnitDescription = (unitBlock) => {
  if (unitBlock) {
    return unitBlock.map((unit) => {
      return (
        <div key={unit.strata}>
          <p
            className={21}
            align="left"
            style={{
              marginLeft: "42.55pt",
              textAlign: "left",
              textIndent: "0in",
            }}
          >
            <b>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Strata:{" "}
              </span>
            </b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              {unit.strata}
            </span>
          </p>
          <p
            className={21}
            align="left"
            style={{
              marginLeft: "42.55pt",
              textAlign: "left",
              textIndent: "0in",
            }}
          >
            <b>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Trial pit No. encountered:{" "}
              </span>
            </b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              {unit.numberOfTrialPits}
            </span>
          </p>
          <p
            className={21}
            align="left"
            style={{
              marginLeft: "42.55pt",
              textAlign: "left",
              textIndent: "0in",
            }}
          >
            <b>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Thickness range:{" "}
              </span>
            </b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              {unit.thicknessRange}
            </span>
          </p>
          <p
            className={21}
            align="left"
            style={{
              marginLeft: "42.55pt",
              textAlign: "left",
              textIndent: "0in",
            }}
          >
            <b>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Underlying:
              </span>
            </b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              {unit.underlying}
            </span>
          </p>
          <p
            className="Legal2"
            style={{ marginLeft: "42.55pt", textIndent: "0in" }}
          >
            <b>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Description:
              </span>
            </b>
            <span
              style={{
                overflow: "visible",
                whiteSpace: "pre-wrap",
                overflowWrap: "break-word",
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
              }}
            >
              {" "}
              {unit.description}
            </span>
          </p>
          <p
            className={21}
            align="left"
            style={{ marginLeft: "0in", textAlign: "left", textIndent: "0in" }}
          >
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
        </div>
      );
    });
  } else return;
};

// Helper function to convert inches measurement into architectural foot format.
const convertToFt = (length) => {
  const a = length / 12;
  const b = Math.floor(a);
  const c = Math.floor((a - b) * 12);
  return `${b}'-${c}"`;
};

// Helper function to render trial pit data within a table
export const trialPitTable = (trialPit) => {
  if (trialPit) {
    return (
      <table className="ui celled table">
        <thead>
          <tr>
            <th>Trial Pit No.</th>
            <th>Groundwater Recharge Level</th>
            <th>Final Depth of Pit</th>
            <th>Competent Stratum Encountered</th>
          </tr>
        </thead>
        <tbody>
          {trialPit.map((item, i) => {
            return (
              <tr className="disabled" key={i}>
                <td>{i + 1}</td>
                <td>{convertToFt(item.groundWaterLevel)}</td>
                <td>{convertToFt(item.finalDepth)}</td>
                <td>{item.bearingStratum}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
};

// export const renderGeoSetting = () => {
// switch (strat)
// }
