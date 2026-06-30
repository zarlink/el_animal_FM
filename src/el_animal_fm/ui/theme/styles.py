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
"""
