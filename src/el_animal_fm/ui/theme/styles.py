from __future__ import annotations


BASE_STYLESHEET = """
QMainWindow {
    background: #05080a;
}

QWidget {
    color: #d7faff;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 13px;
}

#HeaderBar,
#Panel,
#PlaceholderView {
    background: #061012;
    border: 1px solid #b86400;
}

#FundSignalCard {
    background: #061012;
    border: none;
}

#FundCardsScroll,
#FundCardsSurface {
    background: transparent;
    border: none;
}

#FundCardsScroll QScrollBar:vertical {
    background: #061012;
    border-left: 1px solid #173238;
    width: 10px;
    margin: 0;
}

#FundCardsScroll QScrollBar::handle:vertical {
    background: #c96d00;
    min-height: 42px;
}

#FundCardsScroll QScrollBar::add-line:vertical,
#FundCardsScroll QScrollBar::sub-line:vertical {
    height: 0;
}

#FundCardsScroll QScrollBar::add-page:vertical,
#FundCardsScroll QScrollBar::sub-page:vertical {
    background: #061012;
}

#HeaderBar {
    background: #070b0d;
}

#AppTitle {
    color: #ff9500;
    font-size: 32px;
    font-weight: 800;
}

#AppSubtitle,
#PanelTitle,
#CardIndex,
#MetricName,
#StatusLabel {
    color: #18dce8;
    font-weight: 800;
}

#HeaderChip {
    background: #080d10;
    border: 1px solid #4d5358;
    color: #d8e0e4;
    font-size: 15px;
}

#HeaderButton,
#PrimaryHeaderButton {
    background: #120d08;
    border: 1px solid #c96d00;
    color: #ff9500;
    font-weight: 800;
}

#PrimaryHeaderButton {
    border: 2px solid #ff9500;
}

#HeaderButton:hover,
#PrimaryHeaderButton:hover {
    background: #1e1409;
}

#MainNavigation::tab {
    background: #080d10;
    border: 1px solid #9b5b00;
    color: #ff9500;
    min-width: 190px;
    min-height: 36px;
    padding: 3px 18px;
}

#MainNavigation::tab:selected {
    border-color: #18dce8;
    color: #18dce8;
    background: #092024;
}

#ViewHeading,
#CardTitle {
    color: #18dce8;
    font-size: 20px;
    font-weight: 800;
}

#CardIndex {
    font-size: 18px;
}

#MetricValue,
#StatusValue {
    color: #d7faff;
    font-weight: 700;
}

#DecisionLabel {
    color: #ffcc19;
    font-size: 15px;
    font-weight: 800;
}

#DecisionTitle {
    color: #ff9500;
    font-size: 10px;
    font-weight: 800;
}

#SemaforoTitle {
    color: #18dce8;
    font-size: 10px;
    font-weight: 800;
}

#SemaforoResult {
    color: #ffcc19;
    font-size: 19px;
    font-weight: 900;
}

#EmptySurface {
    background: #050a0c;
    border: 1px solid #173238;
}

#LogLine {
    color: #b9f8ff;
    font-size: 12px;
}

#ConsoleLine {
    color: #65ff5f;
    font-size: 12px;
}

#ChartRow,
#MockRow {
    color: #d7faff;
    font-size: 13px;
}

#PipelinePanelTitle,
#PipelineFieldLabel {
    color: #18dce8;
    font-weight: 800;
}

#PipelineInnerPanel {
    background: #050a0c;
    border: 1px solid #173238;
}

#PipelineSeparator {
    color: #173238;
    background: #173238;
    max-height: 1px;
}

#PipelineCheck {
    color: #d7faff;
    spacing: 8px;
}

#PipelineCheck::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #18dce8;
    background: #061012;
}

#PipelineCheck::indicator:checked {
    background: #18dce8;
}

#PipelineInput {
    background: #061012;
    border: 1px solid #173238;
    color: #d7faff;
    min-height: 28px;
    padding-left: 8px;
}

#PipelineValue {
    color: #d7faff;
    font-weight: 700;
}

#PipelinePrimaryButton,
#PipelineButton {
    background: #061012;
    border: 1px solid #18dce8;
    color: #18dce8;
    font-weight: 800;
}

#PipelinePrimaryButton {
    background: #120d08;
    border-color: #ff9500;
    color: #ff9500;
}

#PipelinePrimaryButton:hover,
#PipelineButton:hover {
    background: #092024;
}

#PipelineConsole {
    background: #020506;
    border: none;
    color: #b9f8ff;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 12px;
}

#NewsPanel {
    background: #050a0c;
    border: 1px solid #17646b;
}

#NewsPanelTitle,
#NewsPanelIndex {
    color: #18dce8;
    font-size: 16px;
    font-weight: 900;
}

#NewsPanelIndex {
    background: #092024;
    border: 1px solid #18dce8;
    padding: 3px 8px;
}

#NewsFieldLabel,
#NewsScriptLabel,
#NewsStatLabel {
    color: #18dce8;
    font-size: 11px;
    font-weight: 800;
}

#NewsScriptLabel {
    border-top: 1px solid #173238;
    padding-top: 6px;
}

#NewsSeparator {
    color: #173238;
    background: #173238;
    max-height: 1px;
}

#NewsInput {
    background: #061012;
    border: 1px solid #24535a;
    color: #d7faff;
    min-height: 27px;
    padding: 0 6px;
}

#NewsInput::drop-down {
    border: none;
    width: 18px;
}

#NewsCheck {
    color: #d7faff;
    spacing: 6px;
    font-size: 11px;
}

#NewsCheck::indicator {
    width: 14px;
    height: 14px;
    background: #061012;
    border: 1px solid #18dce8;
}

#NewsCheck::indicator:checked {
    background: #18dce8;
}

#NewsPrimaryButton,
#NewsButton {
    background: #061012;
    border: 1px solid #18dce8;
    color: #18dce8;
    font-weight: 900;
    padding: 4px 10px;
}

#NewsPrimaryButton {
    background: #160e06;
    border: 2px solid #ff9500;
    color: #ff9500;
}

#NewsPrimaryButton:hover,
#NewsButton:hover {
    background: #092024;
}

#NewsStat,
#NewsErrorStat {
    background: #061012;
    border: 1px solid #17646b;
}

#NewsErrorStat {
    border-color: #d94c12;
}

#NewsStatValue {
    color: #65ff5f;
    font-size: 14px;
    font-weight: 900;
}

#NewsCaptcha {
    background: #080d10;
    border: 1px solid #4d5358;
    color: #d8e0e4;
    font-size: 18px;
    letter-spacing: 4px;
    min-height: 40px;
}

#NewsSuccess {
    color: #65ff5f;
    font-size: 11px;
    font-weight: 800;
}

#NewsConsole {
    background: #020506;
    border: 1px solid #173238;
    color: #65ff5f;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 11px;
}
"""
