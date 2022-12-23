import React from "react";
import { connect } from "react-redux";
import { fetchReport } from "../../../actions/index";
import renderUnitDescription from "./renderHelperFunctions";

class ReportShow extends React.Component {
  componentDidMount() {
    this.props.fetchReport(this.props.match.params.id);
    console.log(this.props.report.reportId);
  }

  render() {
    const {
      //Destructuring the values of the report state which has been mapped to props
      report: {
        reportId,
        block,
        parcel,
        siteAddress,
        investigationDate,
        engineerAMR,
        weather,
        investigationDuration,
        trialPitNumber,
        trialPits,
        unitDescriptions,
      },
    } = this.props;

    return (
      <>
        <p>
          {/* Sandbox Code to test if I can iterate over the unitDescriptions array within the report */}
          <meta
            httpEquiv="Content-Type"
            content="text/html; charset=windows-1252"
          />
          <meta name="Generator" content="Microsoft Word 15 (filtered)" />
          <title>CONSTRUCTION REVIEW REPORT NO</title>
          <style
            dangerouslySetInnerHTML={{
              __html:
                '\n<!--\n /* Font Definitions */\n @font-face\n\t{font-family:Wingdings;\n\tpanose-1:5 0 0 0 0 0 0 0 0 0;}\n@font-face\n\t{font-family:SimSun;\n\tpanose-1:2 1 6 0 3 1 1 1 1 1;}\n@font-face\n\t{font-family:"Cambria Math";\n\tpanose-1:2 4 5 3 5 4 6 3 2 4;}\n@font-face\n\t{font-family:"WP MathA";}\n@font-face\n\t{font-family:Univers;}\n@font-face\n\t{font-family:"Arial Black";\n\tpanose-1:2 11 10 4 2 1 2 2 2 4;}\n@font-face\n\t{font-family:"Segoe UI";\n\tpanose-1:2 11 5 2 4 2 4 2 2 3;}\n@font-face\n\t{font-family:"BankGothic Lt BT";}\n@font-face\n\t{font-family:"\\@SimSun";\n\tpanose-1:2 1 6 0 3 1 1 1 1 1;}\n /* Style Definitions */\n p.MsoNormal, li.MsoNormal, div.MsoNormal\n\t{margin:0in;\n\ttext-autospace:none;\n\tfont-size:10.0pt;\n\tfont-family:"Univers",sans-serif;}\np.MsoBodyText, li.MsoBodyText, div.MsoBodyText\n\t{mso-style-link:"Body Text Char";\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:11.0pt;\n\tmargin-left:0in;\n\ttext-align:justify;\n\tfont-size:10.0pt;\n\tfont-family:"Arial",sans-serif;\n\tletter-spacing:-.25pt;}\nem\n\t{font-family:"Arial Black",sans-serif;\n\tfont-style:normal;}\np.MsoListParagraph, li.MsoListParagraph, div.MsoListParagraph\n\t{margin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:.5in;\n\ttext-autospace:none;\n\tfont-size:10.0pt;\n\tfont-family:"Univers",sans-serif;}\np.21, li.21, div.21\n\t{mso-style-name:21;\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:.5in;\n\ttext-align:justify;\n\ttext-indent:-.5in;\n\ttext-autospace:none;\n\tfont-size:10.0pt;\n\tfont-family:"Univers",sans-serif;}\np.31, li.31, div.31\n\t{mso-style-name:31;\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:1.0in;\n\ttext-align:justify;\n\ttext-indent:-.5in;\n\ttext-autospace:none;\n\tfont-size:10.0pt;\n\tfont-family:"Univers",sans-serif;}\np.51, li.51, div.51\n\t{mso-style-name:51;\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:2.5in;\n\ttext-align:justify;\n\ttext-indent:-.5in;\n\ttext-autospace:none;\n\tfont-size:10.0pt;\n\tfont-family:"Univers",sans-serif;}\nspan.BodyTextChar\n\t{mso-style-name:"Body Text Char";\n\tmso-style-link:"Body Text";\n\tfont-family:"Arial",sans-serif;\n\tletter-spacing:-.25pt;}\np.Style1, li.Style1, div.Style1\n\t{mso-style-name:Style1;\n\tmargin:0in;\n\tfont-size:11.0pt;\n\tfont-family:"Courier New";}\np.Legal1, li.Legal1, div.Legal1\n\t{mso-style-name:"Legal 1";\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:21.5pt;\n\ttext-indent:-21.5pt;\n\ttext-autospace:none;\n\tfont-size:12.0pt;\n\tfont-family:"Univers",sans-serif;}\np.Legal2, li.Legal2, div.Legal2\n\t{mso-style-name:"Legal 2";\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:41.3pt;\n\ttext-indent:-41.3pt;\n\ttext-autospace:none;\n\tfont-size:12.0pt;\n\tfont-family:"Univers",sans-serif;}\np.Legal3, li.Legal3, div.Legal3\n\t{mso-style-name:"Legal 3";\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:41.3pt;\n\ttext-indent:-41.3pt;\n\ttext-autospace:none;\n\tfont-size:12.0pt;\n\tfont-family:"Univers",sans-serif;}\np.Legal4, li.Legal4, div.Legal4\n\t{mso-style-name:"Legal 4";\n\tmargin-top:0in;\n\tmargin-right:0in;\n\tmargin-bottom:0in;\n\tmargin-left:55.5pt;\n\ttext-indent:-14.2pt;\n\ttext-autospace:none;\n\tfont-size:12.0pt;\n\tfont-family:"Univers",sans-serif;}\n.MsoChpDefault\n\t{font-size:10.0pt;}\n /* Page Definitions */\n @page WordSection1\n\t{size:8.5in 11.0in;\n\tmargin:42.55pt 56.7pt 58.4pt 70.9pt;}\ndiv.WordSection1\n\t{page:WordSection1;}\n /* List Definitions */\n ol\n\t{margin-bottom:0in;}\nul\n\t{margin-bottom:0in;}\n-->\n',
            }}
          />
        </p>
        <div className="WordSection1">
          <div
            style={{
              border: "none",
              borderBottom: "solid windowtext 1.0pt",
              padding: "0in 0in 1.0pt 0in",
            }}
          >
            <p className="MsoNormal" style={{ border: "none", padding: "0in" }}>
              <b>
                <span
                  style={{
                    fontSize: "8.0pt",
                    fontFamily: '"Arial",sans-serif',
                  }}
                >
                  This Report ({reportId}) must not be construed as altering the
                  contract and is issued solely to draw to your attention any
                  variances from the Contract, requirements observed during our
                  construction review, or, to interpret a Contract requirement.
                  Implementation of any item which may alter the Contract shall
                  not commence until authorized by Change Order. Review has been
                  carried out by examination of selected samples of the Work
                  shown on Contract documents prepared by this firm.
                  Responsibility for compliance with the plans and
                  specifications rests with the Contractor.
                </span>
              </b>
            </p>
          </div>
          <p className="MsoNormal">
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className={21}
            align="left"
            style={{
              marginLeft: "42.55pt",
              textAlign: "left",
              textIndent: "-42.55pt",
            }}
          >
            <span style={{ fontSize: "11.0pt" }}>
              1.1
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              The Geotechnical Investigation of the abovementioned property was
              completed on 15<sup>th</sup>September 2022.{" "}
            </span>
          </p>
          <p className="MsoNormal">
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className={31}
            align="left"
            style={{
              marginLeft: "70.9pt",
              textAlign: "left",
              textIndent: "-28.35pt",
            }}
          >
            <span style={{ fontSize: "11.0pt", fontFamily: "Symbol" }}>
              ·
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Present during the inspection was M. Alexander Moroney of AMR
              Consulting Engineers.
            </span>
          </p>
          <p
            className={51}
            align="left"
            style={{
              marginLeft: "70.9pt",
              textAlign: "left",
              textIndent: "0in",
            }}
          >
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className={31}
            align="left"
            style={{
              marginLeft: "70.9pt",
              textAlign: "left",
              textIndent: "-28.35pt",
            }}
          >
            <span style={{ fontSize: "11.0pt", fontFamily: "Symbol" }}>
              ·
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Weather: {weather}
            </span>
          </p>
          <p className="MsoListParagraph">
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className={31}
            align="left"
            style={{
              marginLeft: "70.9pt",
              textAlign: "left",
              textIndent: "-28.35pt",
            }}
          >
            <span style={{ fontSize: "11.0pt", fontFamily: "Symbol" }}>
              ·
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Investigation lasted approximately 1 hour, starting from 9:00am
              and ending at 10:00am.
            </span>
          </p>
          <p className="MsoNormal">
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className={21}
            align="left"
            style={{
              marginLeft: "42.55pt",
              textAlign: "left",
              textIndent: "-42.55pt",
            }}
          >
            <em>
              <span
                style={{
                  fontSize: "11.0pt",
                  fontFamily: '"Univers",sans-serif',
                }}
              >
                1.2
                <span style={{ font: '7.0pt "Times New Roman"' }}>
                  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                </span>
              </span>
            </em>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              The fieldwork involved in the geotechnical investigation consisted
              of the excavation of {trialPitNumber} No. trial pits using an
              excavator
            </span>
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                {" "}
                supplied by SLIM ltd. Soil descriptions are based on median soil
                gradation and consistencies encountered during the
                investigation.
              </span>
            </em>
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
          {renderUnitDescription(this.props.report.unitDescriptions)}
          {/* <p
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
              NATIVE GROUND, TOPSOIL
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
              1, 2, 3,
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
              0’-2’’
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
              On grade
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
              Loose, off-white, light brown, pinkish-white sandy soil.
              Predominantly rounded coarse sand grains (0.025” to 0.08” dia.).
              Occasional coralline debris and conch shells (up to 8” observed).
              Minor organic contamination within the upper 6” below grade,
              primarily leaf litter. Uniformly graded soil lacking the gradation
              to facilitate compaction, soil not suitable as a bearing stratum.
              If sand is sufficiently cleaned of organic contaminants, it may be
              possible that it can be sold to offset the cost of engineering
              fill.
            </span>
          </p> */}
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
              NATIVE GROUND, HEAVILY CONTAMINATED SAND
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
              All pits
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
              1’-7’ to 3’-3”
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
              On grade, t
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              opsoil
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
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              {" "}
              Loose, light-brown, dark brown, reddish brown sandy soil.
              Predominantly rounded coarse sand grains (0.025” to 0.08” dia.).
              Frequent coralline debris and conch shells (up to 2’’-1”
              observed). High quantity of organic and inorganic contamination
              clearly defined by darker grains, primarily organic silt and
              inorganic Tera Rosa (≤0.002” grains). Gap graded soil consisting
              of compressible organic and inorganic grains lacking gradation to
              promote required compaction. Soil not suitable for reuse within
              soil filling profile.
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
            <u>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                <span style={{ textDecoration: "none" }}>&nbsp;</span>
              </span>
            </u>
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
            <u>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Depth of Trial Pits:
              </span>
            </u>
          </p>
          <table
            className="MsoTableGrid"
            border={1}
            cellSpacing={0}
            cellPadding={0}
            style={{
              marginLeft: "42.55pt",
              borderCollapse: "collapse",
              border: "none",
            }}
          >
            <tbody>
              <tr>
                <td
                  width={147}
                  valign="top"
                  style={{
                    width: "110.2pt",
                    border: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Trial Pit No.
                    </span>
                  </p>
                </td>
                <td
                  width={137}
                  valign="top"
                  style={{
                    width: "102.7pt",
                    border: "solid windowtext 1.0pt",
                    borderLeft: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Groundwater Recharge Level
                    </span>
                  </p>
                </td>
                <td
                  width={145}
                  valign="top"
                  style={{
                    width: "108.75pt",
                    border: "solid windowtext 1.0pt",
                    borderLeft: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Final Depth of Pit
                    </span>
                  </p>
                </td>
                <td
                  width={160}
                  valign="top"
                  style={{
                    width: "119.7pt",
                    border: "solid windowtext 1.0pt",
                    borderLeft: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Competent Stratum Encountered
                    </span>
                  </p>
                </td>
              </tr>
              <tr style={{ height: "29.8pt" }}>
                <td
                  width={147}
                  valign="top"
                  style={{
                    width: "110.2pt",
                    border: "solid windowtext 1.0pt",
                    borderTop: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "29.8pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      1
                    </span>
                  </p>
                </td>
                <td
                  width={137}
                  valign="top"
                  style={{
                    width: "102.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "29.8pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span lang="EN-US">N/A</span>
                  </p>
                </td>
                <td
                  width={145}
                  valign="top"
                  style={{
                    width: "108.75pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "29.8pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      3’-5”
                    </span>
                  </p>
                </td>
                <td
                  width={160}
                  valign="top"
                  style={{
                    width: "119.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "29.8pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Bedrock Encountered at Depth
                    </span>
                  </p>
                </td>
              </tr>
              <tr style={{ height: "27.4pt" }}>
                <td
                  width={147}
                  valign="top"
                  style={{
                    width: "110.2pt",
                    border: "solid windowtext 1.0pt",
                    borderTop: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      2
                    </span>
                  </p>
                </td>
                <td
                  width={137}
                  valign="top"
                  style={{
                    width: "102.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span lang="EN-US">N/A</span>
                  </p>
                </td>
                <td
                  width={145}
                  valign="top"
                  style={{
                    width: "108.75pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      3’-5”
                    </span>
                  </p>
                </td>
                <td
                  width={160}
                  valign="top"
                  style={{
                    width: "119.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Bedrock Encountered at Depth
                    </span>
                  </p>
                </td>
              </tr>
              <tr style={{ height: "27.4pt" }}>
                <td
                  width={147}
                  valign="top"
                  style={{
                    width: "110.2pt",
                    border: "solid windowtext 1.0pt",
                    borderTop: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      3
                    </span>
                  </p>
                </td>
                <td
                  width={137}
                  valign="top"
                  style={{
                    width: "102.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span lang="EN-US">N/A</span>
                  </p>
                </td>
                <td
                  width={145}
                  valign="top"
                  style={{
                    width: "108.75pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      3’-3”
                    </span>
                  </p>
                </td>
                <td
                  width={160}
                  valign="top"
                  style={{
                    width: "119.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Bedrock Encountered at Depth
                    </span>
                  </p>
                </td>
              </tr>
              <tr style={{ height: "27.4pt" }}>
                <td
                  width={147}
                  valign="top"
                  style={{
                    width: "110.2pt",
                    border: "solid windowtext 1.0pt",
                    borderTop: "none",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      4
                    </span>
                  </p>
                </td>
                <td
                  width={137}
                  valign="top"
                  style={{
                    width: "102.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span lang="EN-US">N/A</span>
                  </p>
                </td>
                <td
                  width={145}
                  valign="top"
                  style={{
                    width: "108.75pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className={21}
                    align="center"
                    style={{
                      marginLeft: "0in",
                      textAlign: "center",
                      textIndent: "0in",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      1’-7”
                    </span>
                  </p>
                </td>
                <td
                  width={160}
                  valign="top"
                  style={{
                    width: "119.7pt",
                    borderTop: "none",
                    borderLeft: "none",
                    borderBottom: "solid windowtext 1.0pt",
                    borderRight: "solid windowtext 1.0pt",
                    padding: "0in 5.4pt 0in 5.4pt",
                    height: "27.4pt",
                  }}
                >
                  <p
                    className="MsoNormal"
                    align="center"
                    style={{ textAlign: "center" }}
                  >
                    <span
                      style={{
                        fontSize: "11.0pt",
                        fontFamily: '"Arial",sans-serif',
                      }}
                    >
                      Bedrock Encountered at Depth
                    </span>
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
          <p className="MsoListParagraph" style={{ marginLeft: "42.55pt" }}>
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className="MsoListParagraph"
            style={{ marginLeft: "42.55pt", textIndent: "-42.55pt" }}
          >
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              1.4
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>

            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              Native bedrock was not encountered. Only dense-consolidated Marl
              Fill and Native Marl across the site. Based on the findings of the
              investigation, the dense Ironshore Formation calcrete caprock and
              consolidated marl layer underlies this area; depth approximately
              between <a name="_Hlk95123140">1’</a>
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              {" "}
              –{" "}
            </span>
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              7’’ to 3’
            </span>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              –{" "}
            </span>
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              5”{" "}
            </span>
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              below grade. The Ironshore limestone is the relic of a back reef
              lagoon palaeo setting during the Pleistocene Epoch, a low energy
              environment where fine carbonate sediments would have accumulated
              between high standing Ironshore patch reefs, situated further
              inland during a time of higher sea level, and eventually becoming
              the foundation for mangrove swamps due to the gradual fall in sea
              level. Dense consolidated Native Marl typically has an allowable
              bearing capacity of approximately 8,000psf. The consolidated Marl
              Fill has an estimated bearing capacity of 3,500psf.{" "}
            </span>
          </p>
          <p className="MsoListParagraph" style={{ marginLeft: "42.55pt" }}>
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className="MsoListParagraph"
            style={{
              marginTop: "0in",
              marginRight: "0in",
              marginBottom: "11.0pt",
              marginLeft: "42.55pt",
              textIndent: "-42.55pt",
              textAutospace: "ideograph-numeric ideograph-other",
            }}
          >
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              1.5
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                Given the structural loadings of the proposed building, the
                foundation system should bear upon the underlying dense
                Ironshore Formation limestone encountered between{" "}
              </span>
            </em>
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              1’-7’’ to 3’-5’’
            </span>
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                {" "}
                below grade on this site.{" "}
              </span>
            </em>
            <span
              lang="EN-US"
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Giving consideration for the structural and foundation loadings of
              the proposed development, the recommended foundation option is as
              follows:{" "}
            </span>
          </p>
          <p className="MsoListParagraph">
            <span
              lang="EN-US"
              style={{
                fontSize: "11.0pt",
                fontFamily: '"Arial",sans-serif',
                letterSpacing: "-.25pt",
              }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className="MsoBodyText"
            style={{ marginLeft: "42.55pt", textIndent: "-42.55pt" }}
          >
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              1.6
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <b>
              <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
                STRIP FOOTINGS
              </span>
            </b>
          </p>
          <p className="MsoBodyText" style={{ marginLeft: "42.55pt" }}>
            <span style={{ fontSize: "11.0pt" }}>
              From the findings of this site investigation, another viable
              foundation option is the use of{" "}
              <u>isolated pad footings and linear strip footings</u>, supporting
              a system of masonry super structure walls. The ground floor slab
              will likely be designed as cast on grade.{" "}
            </span>
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                It is therefore recommended that the fill for the foundation
                system should bear on the consolidated native marl encountered
                approximately between{" "}
              </span>
            </em>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              1’-7’’ to 3’-5’’{" "}
            </span>
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                below grade.
              </span>
            </em>
          </p>
          <p className="MsoBodyText" style={{ marginLeft: "42.55pt" }}>
            <span style={{ fontSize: "11.0pt" }}>
              Any topsoil, contaminated sand and or coralline debris encountered
              throughout future earth works should be excavated and replaced
              with suitable engineered fill. After the placement of imported
              engineered fill, additional and thorough compaction is recommended
              across the site followed by a modified proctor test to ensure
              compaction has been achieved (via. TBM Engineering Ltd.). Any
              additional imported fill should consist of well-graded crushed
              stone (e.g. well-graded Marl Fill, Cayman Rock or crusher run).
              This fill material should be suitably compacted and then can be
              used as the means of support for the slab on grade / structure.
              Crusher run fill should be used immediately beneath the slab.
            </span>
          </p>
          <p
            className="MsoBodyText"
            style={{ marginLeft: "1.0in", textIndent: "-.25in" }}
          >
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              a.
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </span>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              It is important to note, when building a foundation system on
              engineered fill there is the possibility of differential
              settlement of the foundation system (this could lead to cracking
              in walls and slabs). If this method is to be used, the following
              technical requirements must be strictly adhered to:
            </span>
          </p>
          <p
            className="MsoBodyText"
            style={{ marginLeft: "1.5in", textIndent: "-1.5in" }}
          >
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
              i.
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;{" "}
              </span>
            </span>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              Well-constructed excavation, safely executed, with all soft and
              hard spots removed, and made reasonably dry and well drained.
            </span>
          </p>
          <p
            className="MsoBodyText"
            style={{ marginLeft: "1.5in", textIndent: "-1.5in" }}
          >
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
              ii.
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;{" "}
              </span>
            </span>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              Sound fill without undesirable material and capable of compaction
              as specified, provided with starting and capping layers as
              necessary.
            </span>
          </p>
          <p
            className="MsoBodyText"
            style={{ marginLeft: "1.5in", textIndent: "-1.5in" }}
          >
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
              iii.
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;{" "}
              </span>
            </span>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              Placement and compaction to ensure that the performance of the
              fill will meet required criteria as a foundation fill (Typically
              95% compaction or greater in layers no greater than 9”). Fill
              material specification to be generated and approved by a
              professional engineer.
            </span>
          </p>
          <p
            className="MsoBodyText"
            style={{ marginLeft: "1.5in", textIndent: "-1.5in" }}
          >
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
              </span>
              iv.
              <span style={{ font: '7.0pt "Times New Roman"' }}>
                &nbsp;&nbsp;&nbsp;&nbsp;{" "}
              </span>
            </span>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              Appropriate monitoring and quality control throughout development.
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
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                See Appendix A for Site Figures
              </span>
            </em>
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
            <em>
              <span
                lang="EN-US"
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                See Appendix B for Limitations
              </span>
            </em>
          </p>
          <p className="MsoBodyText" style={{ marginLeft: "42.55pt" }}>
            <span lang="EN-US" style={{ fontSize: "11.0pt" }}>
              I trust this is satisfactory if you have any questions regarding
              the above or enclosed. Please do not hesitate to contact me.
            </span>
          </p>
          <p className="MsoBodyText" style={{ marginLeft: "42.55pt" }}>
            Yours faithfully,
          </p>
          <p className="Style1" style={{ marginLeft: "42.55pt" }}>
            <span lang="EN-US">
              <img
                width={233}
                height={67}
                id="Picture 3"
                src="NWP%20Duplex%20Report%20Latest%20html_files/image001.jpg"
              />
            </span>
          </p>
          <p className="Style1" style={{ marginLeft: "42.55pt" }}>
            <b>
              <span style={{ fontFamily: '"Arial",sans-serif' }}>
                M. Alexander Moroney,{" "}
              </span>
            </b>
            <i>
              <span style={{ fontFamily: '"Arial",sans-serif' }}>Msc</span>
            </i>
            <b>
              <span style={{ fontFamily: '"Arial",sans-serif' }}> </span>
            </b>
          </p>
          <p className="Style1" style={{ marginLeft: "42.55pt" }}>
            <span style={{ fontFamily: '"Arial",sans-serif' }}>
              Engineering Geologist/ Geotechnical Engineer
            </span>
          </p>
          <p
            className="MsoNormal"
            style={{ marginLeft: "42.55pt", textAlign: "justify" }}
          >
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              &nbsp;
            </span>
          </p>
          <p
            className="MsoNormal"
            style={{ marginLeft: "42.55pt", textAlign: "justify" }}
          >
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              For and on behalf of
            </span>
          </p>
          <p
            className="MsoNormal"
            style={{ marginLeft: "42.55pt", textAlign: "justify" }}
          >
            <b>
              <span
                style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
              >
                AMR Consulting Engineers.
              </span>
            </b>
          </p>
        </div>
      </>
    );
  }
}

const mapStateToProps = (state, ownProps) => {
  return {
    report: state.reports[ownProps.match.params.id],
  };
};

export default connect(mapStateToProps, { fetchReport })(ReportShow);
