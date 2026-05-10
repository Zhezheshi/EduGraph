import { useEffect, useMemo, useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Input,
  Layout,
  Row,
  Space,
  Spin,
  Statistic,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  BuildOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  MessageOutlined,
  PlayCircleOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import api from './api/client.js';
import './App.css';

const { Header, Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Dragger } = Upload;

const BOOK_COLORS = [
  '#4f46e5',
  '#0f766e',
  '#d97706',
  '#dc2626',
  '#7c3aed',
  '#0284c7',
  '#65a30d',
  '#c2410c',
];

const RELATION_LABELS = {
  prerequisite: '前置依赖',
  parallel: '并列关系',
  contains: '包含关系',
  applies_to: '应用关系',
  duplicate: '重复概念',
  complement: '互补关系',
};

function lighten(hex, amount) {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.min(255, (num >> 16) + Math.round(255 * amount));
  const g = Math.min(255, ((num >> 8) & 0xff) + Math.round(255 * amount));
  const b = Math.min(255, (num & 0xff) + Math.round(255 * amount));
  return `rgb(${r},${g},${b})`;
}

function formatPercent(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  return value.toLocaleString('zh-CN');
}

function getBookTone(index) {
  return BOOK_COLORS[index % BOOK_COLORS.length];
}

function getRelationLabel(type) {
  return RELATION_LABELS[type] || type || '关系';
}

export default function App() {
  const [textbooks, setTextbooks] = useState([]);
  const [graphData, setGraphData] = useState(null);
  const [selectedBook, setSelectedBook] = useState('merged');
  const [nodeDetail, setNodeDetail] = useState(null);
  const [activeTab, setActiveTab] = useState('integration');
  const [loading, setLoading] = useState('');
  const [integrationStats, setIntegrationStats] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [ragStatus, setRagStatus] = useState({});
  const [ragAnswer, setRagAnswer] = useState(null);
  const [ragQuestion, setRagQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [report, setReport] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [messageApi, contextHolder] = message.useMessage();

  const refreshAll = async () => {
    try {
      const [books, rag, pipeline] = await Promise.all([
        api.getTextbooks(),
        api.getRagStatus().catch(() => ({})),
        api.getPipelineStatus().catch(() => null),
      ]);
      setTextbooks(books);
      setRagStatus(rag);
      setPipelineStatus(pipeline);
    } catch (error) {
      console.error('refresh failed', error);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  const selectedBookMeta = useMemo(() => {
    if (selectedBook === 'merged') {
      return { title: '跨教材整合图谱', color: '#e11d48' };
    }
    const index = textbooks.findIndex((item) => item.id === selectedBook);
    const book = textbooks.find((item) => item.id === selectedBook);
    return {
      title: book?.title || '未选择教材',
      color: getBookTone(index >= 0 ? index : 0),
    };
  }, [selectedBook, textbooks]);

  const staleWarnings = useMemo(() => {
    const warnings = [];
    if (pipelineStatus?.integration?.stale) {
      warnings.push('整合结果与当前图谱范围不一致，需要重新运行 integration。');
    }
    if (pipelineStatus?.rag?.stale) {
      warnings.push('RAG 索引已过期，需要重新构建索引。');
    }
    return warnings;
  }, [pipelineStatus]);

  const pipelineSummary = pipelineStatus?.summary || {};

  const handleUpload = async (files) => {
    if (!files?.length) return;
    setLoading('上传教材中...');
    try {
      await api.uploadTextbooks(Array.from(files));
      await refreshAll();
      messageApi.success('教材上传成功');
    } catch (error) {
      messageApi.error(`上传失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleParseAll = async () => {
    setLoading('解析教材中...');
    try {
      await api.parseAll(true);
      await refreshAll();
      messageApi.success('教材解析完成');
    } catch (error) {
      messageApi.error(`解析失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleBuildKG = async (bookId) => {
    setLoading(`构建 ${bookId} 图谱中...`);
    try {
      const result = await api.buildKG(bookId, { maxChapters: 3 });
      await refreshAll();
      messageApi.success(`${bookId} 图谱完成：${result.nodes} 节点 / ${result.edges} 边`);
    } catch (error) {
      messageApi.error(`构建失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleBuildAllKG = async () => {
    setLoading('批量构建图谱中...');
    try {
      const result = await api.buildAllKG({ maxChapters: 3 });
      await refreshAll();
      messageApi.success(`批量完成：built ${result.built} / resumed ${result.resumed} / skipped ${result.skipped}`);
    } catch (error) {
      messageApi.error(`批量构建失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleShowGraph = async (bookId) => {
    setSelectedBook(bookId);
    setNodeDetail(null);
    try {
      const data = bookId === 'merged' ? await api.getMergedKG() : await api.getKG(bookId);
      setGraphData(data);
    } catch (error) {
      messageApi.error(`图谱加载失败: ${error.message}`);
    }
  };

  const handleRunIntegration = async () => {
    setLoading('运行跨教材整合中...');
    try {
      const result = await api.runIntegration();
      const [stats, nextDecisions] = await Promise.all([api.getStats(), api.getDecisions()]);
      setIntegrationStats(stats);
      setDecisions(nextDecisions);
      await refreshAll();
      messageApi.success(`整合完成：${result.integrated_nodes} 节点，压缩比 ${result.compression_ratio}`);
    } catch (error) {
      messageApi.error(`整合失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleBuildRAGIndex = async () => {
    setLoading('构建 RAG 索引中...');
    try {
      const status = await api.buildIndex({ maxChapters: 3 });
      setRagStatus(status);
      await refreshAll();
      messageApi.success(`RAG 索引完成：${status.total_chunks} chunks`);
    } catch (error) {
      messageApi.error(`索引构建失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleRAGQuery = async () => {
    if (!ragQuestion.trim()) return;
    setLoading('检索并生成回答中...');
    try {
      const response = await api.query(ragQuestion);
      setRagAnswer(response);
    } catch (error) {
      messageApi.error(`问答失败: ${error.message}`);
    } finally {
      setLoading('');
    }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const userInput = chatInput;
    setChatHistory((prev) => [...prev, { role: 'user', content: userInput }]);
    setChatInput('');

    try {
      const response = await api.sendChat(userInput);
      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: response.reply, actions: response.actions_taken || [] },
      ]);
    } catch (error) {
      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: `发送失败: ${error.message}`, actions: [] },
      ]);
    }
  };

  const handleLoadReport = async () => {
    try {
      const data = await api.getReport();
      setReport(data);
    } catch (error) {
      messageApi.error(`报告加载失败: ${error.message}`);
    }
  };

  const buildGraphOption = () => {
    if (!graphData?.nodes?.length) return null;

    const categoryMap = {};
    graphData.nodes.forEach((node) => {
      const key = node.textbook_id || 'integrated';
      if (!(key in categoryMap)) {
        categoryMap[key] = Object.keys(categoryMap).length;
      }
    });

    const nodes = graphData.nodes.map((node) => {
      const colorIndex = categoryMap[node.textbook_id || 'integrated'] || 0;
      const color = BOOK_COLORS[colorIndex % BOOK_COLORS.length];
      const size = Math.min(58, Math.max(18, 18 + (node.frequency || 1) * 6 + (node.importance || 0.5) * 14));

      return {
        id: node.id,
        name: node.name,
        category: colorIndex,
        symbolSize: size,
        itemStyle: {
          color: {
            type: 'radial',
            x: 0.35,
            y: 0.3,
            r: 0.85,
            colorStops: [
              { offset: 0, color: lighten(color, 0.22) },
              { offset: 1, color },
            ],
          },
          borderColor: 'rgba(255,255,255,0.72)',
          borderWidth: 2,
          shadowBlur: 16,
          shadowColor: `${color}55`,
        },
        label: {
          show: size >= 28,
          color: '#e5eefb',
          fontSize: size >= 36 ? 12 : 10,
          formatter: ({ name }) => (name.length > 10 ? `${name.slice(0, 10)}…` : name),
        },
        data: node,
      };
    });

    const validNodeIds = new Set(nodes.map((node) => node.id));
    const links = (graphData.edges || [])
      .filter((edge) => validNodeIds.has(edge.source) && validNodeIds.has(edge.target))
      .map((edge) => ({
        source: edge.source,
        target: edge.target,
        lineStyle: {
          color: '#5b708a',
          opacity: 0.28,
          width: 1.2,
          curveness: 0.18,
        },
        emphasis: {
          lineStyle: { opacity: 0.9, width: 2.4 },
        },
        data: edge,
      }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(9, 18, 32, 0.96)',
        borderColor: '#24354f',
        borderWidth: 1,
        textStyle: { color: '#eef4ff', fontSize: 12 },
        formatter: (params) => {
          if (params.dataType === 'node') {
            const data = params.data.data;
            return `
              <div style="max-width: 280px">
                <div style="font-size:14px;font-weight:600;margin-bottom:6px">${data.name}</div>
                <div style="color:#9fb0c8;font-size:11px;margin-bottom:6px">${data.category || '知识点'}</div>
                <div style="line-height:1.6">${(data.definition || '暂无定义').slice(0, 120)}${(data.definition || '').length > 120 ? '...' : ''}</div>
                <div style="margin-top:8px;color:#7284a0;font-size:11px">${data.textbook_id || ''} · ${data.chapter || ''} · 第 ${data.page || '?'} 页</div>
              </div>
            `;
          }

          const edge = params.data?.data || {};
          return `
            <div>
              <div style="font-weight:600;margin-bottom:4px">${getRelationLabel(edge.relation_type)}</div>
              <div style="color:#9fb0c8;font-size:11px">${edge.description || '无关系描述'}</div>
            </div>
          `;
        },
      },
      legend: {
        top: 14,
        left: 'center',
        itemWidth: 12,
        itemHeight: 8,
        icon: 'roundRect',
        textStyle: { color: '#8fa3bf', fontSize: 11 },
        data: Object.keys(categoryMap),
      },
      animationDuration: 1200,
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        data: nodes,
        links,
        force: {
          repulsion: 280,
          gravity: 0.08,
          edgeLength: [60, 180],
          friction: 0.65,
          layoutAnimation: true,
        },
        emphasis: {
          focus: 'adjacency',
          itemStyle: {
            shadowBlur: 22,
            borderWidth: 3,
          },
          lineStyle: {
            width: 2.8,
            opacity: 0.88,
          },
          label: { show: true, fontSize: 13, fontWeight: 700 },
        },
        blur: {
          itemStyle: { opacity: 0.12 },
          lineStyle: { opacity: 0.05 },
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 5,
      }],
    };
  };

  const tabItems = [
    {
      key: 'integration',
      label: <span><PlayCircleOutlined /> 整合</span>,
      children: (
        <div className="panel-scroll">
          <Card className="panel-card">
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRunIntegration} block>
                运行跨教材整合
              </Button>
              <Row gutter={12}>
                <Col span={8}>
                  <Statistic title="原始节点" value={integrationStats?.original_node_count || pipelineStatus?.integration?.original_node_count || 0} />
                </Col>
                <Col span={8}>
                  <Statistic title="整合后" value={integrationStats?.integrated_node_count || pipelineStatus?.integration?.integrated_node_count || 0} />
                </Col>
                <Col span={8}>
                  <Statistic title="压缩比" value={formatPercent(integrationStats?.compression_ratio ?? pipelineStatus?.integration?.compression_ratio)} />
                </Col>
              </Row>
              <Space wrap>
                <Tag color="blue">决策 {decisions.length || pipelineStatus?.integration?.decisions || 0}</Tag>
                <Tag color={pipelineStatus?.integration?.stale ? 'red' : 'green'}>
                  {pipelineStatus?.integration?.stale ? '整合结果已过期' : '整合结果可用'}
                </Tag>
              </Space>
            </Space>
          </Card>

          <Card className="panel-card" title="整合决策">
            {decisions.length ? (
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                {decisions.map((decision) => (
                  <div key={decision.decision_id} className="decision-row">
                    <Space align="center" size={8}>
                      <Tag color={decision.action === 'merge' ? 'blue' : decision.action === 'keep' ? 'green' : 'orange'}>
                        {decision.action}
                      </Tag>
                      <Text type="secondary">{formatPercent(decision.confidence)}</Text>
                    </Space>
                    <Paragraph ellipsis={{ rows: 2, expandable: true }} style={{ marginBottom: 0 }}>
                      {decision.reason || '暂无说明'}
                    </Paragraph>
                  </div>
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未加载整合决策" />
            )}
          </Card>
        </div>
      ),
    },
    {
      key: 'rag',
      label: <span><QuestionCircleOutlined /> 问答</span>,
      children: (
        <div className="panel-scroll">
          <Card className="panel-card">
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Button onClick={handleBuildRAGIndex} icon={<BuildOutlined />} block>
                重建 RAG 索引
              </Button>
              <Space wrap>
                <Tag color="purple">教材 {ragStatus.total_textbooks || 0}</Tag>
                <Tag color="blue">Chunks {ragStatus.total_chunks || 0}</Tag>
                <Tag color={pipelineStatus?.rag?.stale ? 'orange' : 'green'}>
                  {pipelineStatus?.rag?.stale ? '索引已过期' : '索引可用'}
                </Tag>
              </Space>
              <Input.Search
                value={ragQuestion}
                onChange={(event) => setRagQuestion(event.target.value)}
                onSearch={handleRAGQuery}
                enterButton="提问"
                placeholder="输入教材问答问题，例如：什么是炎症？"
              />
            </Space>
          </Card>

          {ragAnswer ? (
            <>
              <Card className="panel-card" title="回答">
                <Paragraph className="answer-text">{ragAnswer.answer}</Paragraph>
              </Card>
              <Card className="panel-card" title="引用来源">
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  {(ragAnswer.citations || []).map((citation, index) => (
                    <div key={`${citation.textbook}-${index}`} className="citation-row">
                      <Space wrap>
                        <Tag>{citation.textbook}</Tag>
                        <Text type="secondary">{citation.chapter} · 第 {citation.page} 页</Text>
                        <Text type="secondary">相关度 {formatPercent(citation.relevance_score)}</Text>
                      </Space>
                      <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
                        {citation.chunk_preview}
                      </Paragraph>
                    </div>
                  ))}
                </Space>
              </Card>
            </>
          ) : (
            <Card className="panel-card">
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="输入问题后查看回答与引用来源" />
            </Card>
          )}
        </div>
      ),
    },
    {
      key: 'chat',
      label: <span><MessageOutlined /> 教师对话</span>,
      children: (
        <div className="panel-scroll chat-panel">
          <Card className="panel-card chat-history-card">
            <div className="chat-history">
              {chatHistory.length ? (
                chatHistory.map((item, index) => (
                  <div key={`${item.role}-${index}`} className={`chat-bubble ${item.role}`}>
                    <Text strong>{item.role === 'user' ? '教师' : 'Agent'}</Text>
                    <Paragraph style={{ marginBottom: 0, marginTop: 6 }}>{item.content}</Paragraph>
                    {item.actions?.length ? (
                      <div className="chat-actions">
                        {item.actions.map((action, actionIndex) => (
                          <Tag key={`${action}-${actionIndex}`} color="blue">{action}</Tag>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未开始教师对话" />
              )}
            </div>
          </Card>
          <Card className="panel-card">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <TextArea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                rows={4}
                placeholder="输入教师反馈，例如：请解释为什么合并这两个知识点。"
              />
              <Button type="primary" onClick={handleChat}>
                发送反馈
              </Button>
            </Space>
          </Card>
        </div>
      ),
    },
    {
      key: 'report',
      label: <span><FileTextOutlined /> 报告</span>,
      children: (
        <div className="panel-scroll">
          <Card className="panel-card">
            <Button onClick={handleLoadReport} icon={<ReloadOutlined />} block>
              刷新报告数据
            </Button>
          </Card>
          {report ? (
            <>
              <Card className="panel-card" title="整合概览">
                <Row gutter={[12, 12]}>
                  <Col span={12}><Statistic title="原始总字数" value={report.stats?.original_total_chars || 0} formatter={formatNumber} /></Col>
                  <Col span={12}><Statistic title="整合后字数" value={report.stats?.integrated_total_chars || 0} formatter={formatNumber} /></Col>
                  <Col span={8}><Statistic title="合并" value={report.stats?.merge_count || 0} /></Col>
                  <Col span={8}><Statistic title="保留" value={report.stats?.keep_count || 0} /></Col>
                  <Col span={8}><Statistic title="删除" value={report.stats?.remove_count || 0} /></Col>
                </Row>
              </Card>
              <Card className="panel-card" title="报告摘要">
                <Paragraph>当前系统已经纳入 {pipelineSummary.registered_books || 0} 本教材，完成解析 {pipelineSummary.parsed_books || 0} 本、图谱构建 {pipelineSummary.graph_books || 0} 本。</Paragraph>
                <Paragraph>最新整合结果包含 {report.stats?.total_decisions || 0} 条决策，当前压缩比为 {formatPercent(pipelineStatus?.integration?.compression_ratio)}。</Paragraph>
              </Card>
              <Card className="panel-card" title="关键案例">
                {report.key_cases?.length ? (
                  <Space direction="vertical" size={10} style={{ width: '100%' }}>
                    {report.key_cases.map((item) => (
                      <div key={item.decision_id} className="decision-row">
                        <Space align="center" size={8}>
                          <Tag>{item.action}</Tag>
                          <Text type="secondary">{formatPercent(item.confidence)}</Text>
                        </Space>
                        <Paragraph style={{ marginBottom: 0 }}>{item.reason}</Paragraph>
                      </div>
                    ))}
                  </Space>
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无关键案例" />
                )}
              </Card>
            </>
          ) : (
            <Card className="panel-card">
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击上方按钮加载报告数据" />
            </Card>
          )}
        </div>
      ),
    },
  ];

  return (
    <Layout className="app-shell">
      {contextHolder}
      {loading ? (
        <div className="loading-overlay">
          <Spin size="large" tip={loading} />
        </div>
      ) : null}

      <Header className="app-header">
        <div className="header-brand">
          <div className="header-mark">EG</div>
          <div>
            <Title level={4} style={{ margin: 0, color: '#f8fbff' }}>EduGraph Agent</Title>
            <Text className="header-subtitle">多教材知识整合工作台</Text>
          </div>
        </div>
        <Space wrap size={[10, 10]}>
          <Tag color="blue">教材 {pipelineSummary.registered_books || 0}</Tag>
          <Tag color="green">解析 {pipelineSummary.parsed_books || 0}</Tag>
          <Tag color="gold">图谱 {pipelineSummary.graph_books || 0}</Tag>
          <Tag color="purple">RAG {ragStatus.total_chunks || 0}</Tag>
          <Button icon={<ReloadOutlined />} onClick={refreshAll}>刷新状态</Button>
        </Space>
      </Header>

      <Content className="workspace">
        <section className="hero-strip">
          <div className="hero-copy">
            <Text className="eyebrow">Current Run</Text>
            <Title level={2}>全屏知识图谱工作台</Title>
            <Paragraph>
              当前页面已调整为全屏填充布局，左侧管理教材与流程，中间展示图谱，右侧展示整合、RAG、对话与报告，
              不再只是一条中间工作带。
            </Paragraph>
            <Space wrap>
              <Badge status={pipelineStatus?.integration?.stale ? 'error' : 'success'} text={pipelineStatus?.integration?.stale ? '整合待刷新' : '整合已同步'} />
              <Badge status={pipelineStatus?.rag?.stale ? 'warning' : 'success'} text={pipelineStatus?.rag?.stale ? 'RAG 待重建' : 'RAG 已同步'} />
            </Space>
          </div>
          <div className="hero-stats">
            <Card className="metric-card"><Statistic title="已注册教材" value={pipelineSummary.registered_books || 0} /></Card>
            <Card className="metric-card"><Statistic title="图谱节点" value={graphData?.nodes?.length || pipelineStatus?.integration?.integrated_node_count || 0} /></Card>
            <Card className="metric-card"><Statistic title="压缩比" value={formatPercent(pipelineStatus?.integration?.compression_ratio)} /></Card>
            <Card className="metric-card"><Statistic title="RAG Chunks" value={ragStatus.total_chunks || 0} /></Card>
          </div>
        </section>

        {staleWarnings.length ? (
          <div className="warning-stack">
            {staleWarnings.map((warning) => (
              <Alert key={warning} type="warning" showIcon message={warning} />
            ))}
          </div>
        ) : null}

        <section className="workspace-grid">
          <aside className="left-column">
            <Card className="workspace-card panel-card-fill" title="教材与流程">
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Dragger
                  multiple
                  showUploadList={false}
                  accept=".pdf,.txt,.md"
                  beforeUpload={(file) => {
                    handleUpload([file]);
                    return false;
                  }}
                  className="upload-dragger"
                >
                  <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                  <p className="ant-upload-text">拖拽教材到这里，或点击上传</p>
                  <p className="ant-upload-hint">支持 PDF / TXT / Markdown</p>
                </Dragger>

                <Row gutter={[10, 10]}>
                  <Col span={12}>
                    <Button block onClick={handleParseAll}>解析全部</Button>
                  </Col>
                  <Col span={12}>
                    <Button block type="primary" icon={<BuildOutlined />} onClick={handleBuildAllKG}>批量建图</Button>
                  </Col>
                </Row>

                <Divider style={{ margin: '4px 0 0' }} />
                <div className="book-list">
                  {textbooks.map((book, index) => {
                    const statusItem = pipelineStatus?.textbooks?.find((item) => item.book_id === book.id);
                    const tone = getBookTone(index);
                    return (
                      <div
                        key={book.id}
                        className={`book-row ${selectedBook === book.id ? 'active' : ''}`}
                        style={{ '--tone': tone }}
                        onClick={() => handleShowGraph(book.id)}
                      >
                        <div className="book-row-main">
                          <Text strong>{book.title}</Text>
                          <Text type="secondary">{book.total_pages || statusItem?.parsed?.total_pages || 0} 页 · {book.total_chars ? formatNumber(book.total_chars) : '--'} 字</Text>
                          <div className="book-meta-inline">
                            <Tag color={book.status === 'parsed' ? 'green' : 'blue'}>{book.status}</Tag>
                            <Tag>{statusItem?.knowledge_graph?.chapters_processed || 0}/{statusItem?.knowledge_graph?.chapters_total || 0} 章图谱</Tag>
                          </div>
                        </div>
                        <div className="book-actions">
                          <Button size="small" type="link" onClick={(event) => { event.stopPropagation(); handleBuildKG(book.id); }}>建图</Button>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <Button icon={<CloudServerOutlined />} onClick={() => handleShowGraph('merged')} block type={selectedBook === 'merged' ? 'primary' : 'default'}>
                  查看整合图谱
                </Button>
              </Space>
            </Card>
          </aside>

          <main className="graph-column">
            <Card className="workspace-card graph-card" bodyStyle={{ padding: 0, height: '100%' }}>
              <div className="graph-topbar">
                <div>
                  <Text className="graph-topbar-label">Knowledge Graph</Text>
                  <Title level={4} style={{ margin: 0, color: '#eef5ff' }}>{selectedBookMeta.title}</Title>
                </div>
                <Space wrap>
                  <Tag color="processing">{graphData?.nodes?.length || 0} 节点</Tag>
                  <Tag color="success">{graphData?.edges?.length || 0} 边</Tag>
                </Space>
              </div>

              <div className="graph-stage">
                {graphData?.nodes?.length ? (
                  <ReactEChartsCore
                    option={buildGraphOption()}
                    style={{ height: '100%', minHeight: 560 }}
                    notMerge
                    onEvents={{
                      click: (params) => {
                        if (params.dataType === 'node' && params.data?.data) {
                          setNodeDetail(params.data.data);
                        }
                      },
                    }}
                  />
                ) : (
                  <Empty className="graph-empty" description="选择教材或整合图谱开始查看" />
                )}
              </div>

              {nodeDetail ? (
                <div className="detail-drawer">
                  <div className="detail-header">
                    <div>
                      <Text className="detail-kicker">节点详情</Text>
                      <Title level={5} style={{ margin: 0 }}>{nodeDetail.name}</Title>
                    </div>
                    <Button size="small" type="text" onClick={() => setNodeDetail(null)}>关闭</Button>
                  </div>
                  <Space wrap size={[8, 8]}>
                    <Tag>{nodeDetail.category || '知识点'}</Tag>
                    <Tag>{nodeDetail.textbook_id || 'integrated'}</Tag>
                    <Tag>{nodeDetail.chapter || '未知章节'}</Tag>
                  </Space>
                  <Paragraph style={{ marginTop: 12, marginBottom: 10 }}>{nodeDetail.definition || '暂无定义'}</Paragraph>
                  <Text type="secondary">第 {nodeDetail.page || '?'} 页 · 频次 {nodeDetail.frequency || 1} · 重要度 {nodeDetail.importance || 0}</Text>
                </div>
              ) : null}
            </Card>
          </main>

          <aside className="right-column">
            <Card className="workspace-card panel-card-fill" bodyStyle={{ padding: 0 }}>
              <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} className="side-tabs" />
              <div className="status-rail">
                <Text type="secondary">
                  Pipeline：解析 {pipelineSummary.parsed_books || 0}/{pipelineSummary.registered_books || 0} · 图谱 {pipelineSummary.graph_books || 0} · 局部图谱 {pipelineSummary.partial_graph_books || 0}
                </Text>
              </div>
            </Card>
          </aside>
        </section>
      </Content>
    </Layout>
  );
}
