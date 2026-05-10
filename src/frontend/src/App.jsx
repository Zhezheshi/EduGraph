import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
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
  Select,
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

function getRelationLabel(type) {
  return RELATION_LABELS[type] || type || '关系';
}

function buildReportMarkdown(report, pipelineStatus) {
  if (!report) return '';

  const summary = pipelineStatus?.summary || {};
  const integration = pipelineStatus?.integration || {};
  const stats = report.stats || {};
  const cases = report.key_cases || [];

  const lines = [
    '# 多教材整合摘要',
    '',
    `- 已注册教材：${summary.registered_books || 0} 本`,
    `- 已解析教材：${summary.parsed_books || 0} 本`,
    `- 已构建图谱：${summary.graph_books || 0} 本`,
    `- 当前整合范围：${(integration.book_ids || []).join('、') || '暂无'}`,
    `- 原始节点数：${formatNumber(integration.original_node_count || 0)}`,
    `- 整合后节点数：${formatNumber(integration.integrated_node_count || 0)}`,
    `- 压缩比：${formatPercent(integration.compression_ratio)}`,
    '',
    '## 决策统计',
    '',
    `- 总决策数：${formatNumber(stats.total_decisions || 0)}`,
    `- 合并：${formatNumber(stats.merge_count || 0)}`,
    `- 保留：${formatNumber(stats.keep_count || 0)}`,
    `- 删除：${formatNumber(stats.remove_count || 0)}`,
    '',
    '## 关键案例',
    '',
  ];

  if (!cases.length) {
    lines.push('- 当前没有可展示的关键案例。');
  } else {
    cases.forEach((item) => {
      lines.push(`- **${item.action} / ${formatPercent(item.confidence)}**：${item.reason || '暂无说明'}`);
    });
  }

  return lines.join('\n');
}

export default function App() {
  const [textbooks, setTextbooks] = useState([]);
  const [graphData, setGraphData] = useState(null);
  const [selectedBook, setSelectedBook] = useState('merged');
  const [selectedChapters, setSelectedChapters] = useState(null);
  const [nodeDetail, setNodeDetail] = useState(null);
  const [graphSearch, setGraphSearch] = useState('');
  const [graphBookFilter, setGraphBookFilter] = useState([]);
  const [activeTab, setActiveTab] = useState('integration');
  const [busy, setBusy] = useState('');
  const [actionLoading, setActionLoading] = useState({});
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

  const setButtonBusy = (key, value) => {
    setActionLoading((prev) => ({ ...prev, [key]: value }));
  };

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

  useEffect(() => {
    if (pipelineStatus?.integration?.exists && !decisions.length) {
      refreshIntegrationData().catch(() => {});
    }
  }, [pipelineStatus]);

  const selectedBookMeta = useMemo(() => {
    if (selectedBook === 'merged') {
      return { title: '跨教材整合图谱', color: '#e11d48' };
    }
    const book = textbooks.find((item) => item.id === selectedBook);
    const index = textbooks.findIndex((item) => item.id === selectedBook);
    return {
      title: book?.title || '未选择教材',
      color: BOOK_COLORS[(index >= 0 ? index : 0) % BOOK_COLORS.length],
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
  const reportMarkdown = useMemo(() => buildReportMarkdown(report, pipelineStatus), [report, pipelineStatus]);

  const handleUpload = async (files) => {
    if (!files?.length) return;
    setBusy('上传教材中...');
    try {
      await api.uploadTextbooks(Array.from(files));
      await refreshAll();
      messageApi.success('教材上传成功');
    } catch (error) {
      messageApi.error(`上传失败：${error.message}`);
    } finally {
      setBusy('');
    }
  };

  const handleParseAll = async () => {
    setButtonBusy('parseAll', true);
    try {
      await api.parseAll(true);
      await refreshAll();
      messageApi.success('教材解析完成');
    } catch (error) {
      messageApi.error(`解析失败：${error.message}`);
    } finally {
      setButtonBusy('parseAll', false);
    }
  };

  const handleBuildAllKG = async () => {
    setButtonBusy('buildAllKG', true);
    try {
      const result = await api.buildAllKG({ maxChapters: 3 });
      await refreshAll();
      messageApi.success(`批量完成：built ${result.built} / resumed ${result.resumed} / skipped ${result.skipped}`);
    } catch (error) {
      messageApi.error(`批量构建失败：${error.message}`);
    } finally {
      setButtonBusy('buildAllKG', false);
    }
  };

  const handleBuildKG = async (bookId) => {
    setButtonBusy(`build:${bookId}`, true);
    try {
      const result = await api.buildKG(bookId, { maxChapters: 3 });
      await refreshAll();
      if (selectedBook === bookId) {
        const chapterData = await api.getKGChapters(bookId).catch(() => null);
        setSelectedChapters(chapterData);
      }
      messageApi.success(`${bookId} 图谱完成：${result.nodes} 节点 / ${result.edges} 边`);
    } catch (error) {
      messageApi.error(`构建失败：${error.message}`);
    } finally {
      setButtonBusy(`build:${bookId}`, false);
    }
  };

  const handleDeleteTextbook = async (bookId) => {
    setButtonBusy(`delete:${bookId}`, true);
    try {
      const result = await api.deleteTextbook(bookId);
      if (selectedBook === bookId) {
        setSelectedBook('merged');
        setSelectedChapters(null);
        setGraphData(null);
        setNodeDetail(null);
      }
      await refreshAll();
      if (result.integration_invalidated || result.rag_invalidated) {
        messageApi.warning(`教材已删除，${result.integration_invalidated ? '整合结果' : ''}${result.integration_invalidated && result.rag_invalidated ? '和' : ''}${result.rag_invalidated ? 'RAG 索引' : ''}已失效。`);
      } else {
        messageApi.success('教材已删除');
      }
    } catch (error) {
      messageApi.error(`删除失败：${error.message}`);
    } finally {
      setButtonBusy(`delete:${bookId}`, false);
    }
  };

  const handleShowGraph = async (bookId) => {
    setSelectedBook(bookId);
    setNodeDetail(null);
    setBusy('加载图谱中...');
    try {
      const [graph, chapterData] = await Promise.all([
        bookId === 'merged' ? api.getMergedKG() : api.getKG(bookId),
        bookId === 'merged' ? Promise.resolve(null) : api.getKGChapters(bookId).catch(() => null),
      ]);
      setGraphData(graph);
      setSelectedChapters(chapterData);
    } catch (error) {
      messageApi.error(`图谱加载失败：${error.message}`);
    } finally {
      setBusy('');
    }
  };

  const handleRunIntegration = async () => {
    setButtonBusy('integration', true);
    try {
      const result = await api.runIntegration();
      await refreshIntegrationData();
      await refreshAll();
      messageApi.success(`整合完成：${result.integrated_nodes} 节点，压缩比 ${result.compression_ratio}`);
    } catch (error) {
      messageApi.error(`整合失败：${error.message}`);
    } finally {
      setButtonBusy('integration', false);
    }
  };

  const refreshIntegrationData = async () => {
    const [stats, nextDecisions] = await Promise.all([
      api.getStats().catch(() => null),
      api.getDecisions().catch(() => []),
    ]);
    setIntegrationStats(stats);
    setDecisions(nextDecisions);
  };

  const handleDecisionStatus = async (decisionId, action) => {
    const key = `${action}:${decisionId}`;
    setButtonBusy(key, true);
    try {
      if (action === 'accept') {
        await api.acceptDecision(decisionId);
      } else {
        await api.rejectDecision(decisionId);
      }
      await refreshIntegrationData();
      await refreshAll();
      messageApi.success(`决策已${action === 'accept' ? '接受' : '驳回'}`);
    } catch (error) {
      messageApi.error(`操作失败：${error.message}`);
    } finally {
      setButtonBusy(key, false);
    }
  };

  const handleBuildRAGIndex = async () => {
    setButtonBusy('ragIndex', true);
    try {
      const status = await api.buildIndex({ maxChapters: 3 });
      setRagStatus(status);
      await refreshAll();
      messageApi.success(`RAG 索引完成：${status.total_chunks} 个 chunks`);
    } catch (error) {
      messageApi.error(`索引构建失败：${error.message}`);
    } finally {
      setButtonBusy('ragIndex', false);
    }
  };

  const handleRAGQuery = async () => {
    if (!ragQuestion.trim()) return;
    setButtonBusy('ragQuery', true);
    try {
      const response = await api.query(ragQuestion);
      setRagAnswer(response);
    } catch (error) {
      messageApi.error(`问答失败：${error.message}`);
    } finally {
      setButtonBusy('ragQuery', false);
    }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const userInput = chatInput;
    setChatHistory((prev) => [...prev, { role: 'user', content: userInput }]);
    setChatInput('');
    setButtonBusy('chat', true);
    try {
      const response = await api.sendChat(userInput);
      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: response.reply, actions: response.actions_taken || [] },
      ]);
    } catch (error) {
      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: `发送失败：${error.message}`, actions: [] },
      ]);
    } finally {
      setButtonBusy('chat', false);
    }
  };

  const handleLoadReport = async () => {
    setButtonBusy('report', true);
    try {
      const data = await api.getReport();
      setReport(data);
    } catch (error) {
      messageApi.error(`报告加载失败：${error.message}`);
    } finally {
      setButtonBusy('report', false);
    }
  };

  const buildGraphOption = () => {
    if (!graphData?.nodes?.length) return null;

    const searchLower = graphSearch.toLowerCase();
    const hasFilter = graphBookFilter.length > 0;
    const hasSearch = searchLower.length > 0;

    const categoryMap = {};
    graphData.nodes.forEach((node) => {
      const key = node.textbook_id || 'integrated';
      if (!(key in categoryMap)) categoryMap[key] = Object.keys(categoryMap).length;
    });

    const nodes = graphData.nodes.map((node) => {
      const colorIndex = categoryMap[node.textbook_id || 'integrated'] || 0;
      const color = BOOK_COLORS[colorIndex % BOOK_COLORS.length];
      const size = Math.min(58, Math.max(18, 18 + (node.frequency || 1) * 6 + (node.importance || 0.5) * 14));

      const matchesFilter = !hasFilter || graphBookFilter.includes(node.textbook_id);
      const matchesSearch = !hasSearch || (node.name || '').toLowerCase().includes(searchLower);
      const visible = matchesFilter;
      const highlighted = hasSearch && matchesSearch;

      return {
        id: node.id,
        name: node.name,
        category: colorIndex,
        symbolSize: visible ? size : 0,
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
          borderColor: highlighted ? '#facc15' : 'rgba(255,255,255,0.72)',
          borderWidth: highlighted ? 3 : 2,
          shadowBlur: highlighted ? 24 : 16,
          shadowColor: highlighted ? '#facc1588' : `${color}55`,
          opacity: hasSearch && !highlighted ? 0.18 : 1,
        },
        label: {
          show: size >= 28 && visible,
          color: highlighted ? '#facc15' : '#e5eefb',
          fontSize: highlighted ? 13 : size >= 36 ? 12 : 10,
          fontWeight: highlighted ? 700 : undefined,
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

  const sankeyOption = useMemo(() => {
    if (!decisions.length || !textbooks.length) return null;

    const bookNodeMap = {};
    textbooks.forEach((b, i) => {
      bookNodeMap[b.id] = { name: b.title, index: i };
    });

    const sourceNodes = textbooks.map((b) => ({
      name: b.title,
      itemStyle: { color: BOOK_COLORS[textbooks.indexOf(b) % BOOK_COLORS.length] },
    }));

    const targetNames = ['已合并', '已保留', '已移除'];
    const targetColors = ['#3b82f6', '#10b981', '#f59e0b'];
    const targetNodes = targetNames.map((n, i) => ({
      name: n,
      itemStyle: { color: targetColors[i] },
    }));

    const actionToTarget = { merge: '已合并', keep: '已保留', remove: '已移除' };
    const linkCount = {};
    decisions.forEach((d) => {
      const target = actionToTarget[d.action] || '已保留';
      (d.source_textbooks || []).forEach((tbTitle) => {
        const key = `${tbTitle}|||${target}`;
        linkCount[key] = (linkCount[key] || 0) + 1;
      });
    });

    const links = Object.entries(linkCount).map(([key, value]) => {
      const [source, target] = key.split('|||');
      return { source, target, value };
    });

    if (!links.length) return null;

    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', triggerOn: 'mousemove' },
      series: [{
        type: 'sankey',
        layout: 'none',
        emphasis: { focus: 'adjacency' },
        nodeAlign: 'left',
        nodeWidth: 20,
        nodeGap: 14,
        layoutIterations: 0,
        label: {
          color: '#334155',
          fontSize: 12,
          formatter: ({ name }) => name.length > 8 ? `${name.slice(0, 8)}…` : name,
        },
        lineStyle: { color: 'gradient', opacity: 0.35, curveness: 0.5 },
        data: [...sourceNodes, ...targetNodes],
        links,
      }],
    };
  }, [decisions, textbooks]);

  const tabItems = [
    {
      key: 'integration',
      label: <span><PlayCircleOutlined /> 整合</span>,
      children: (
        <div className="panel-scroll">
          <Card className="panel-card">
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRunIntegration} loading={!!actionLoading.integration} block>
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

          <Card className="panel-card" title="整合前后对比">
            {sankeyOption ? (
              <ReactEChartsCore
                option={sankeyOption}
                style={{ height: 220 }}
                notMerge
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无整合数据生成对比图" />
            )}
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
                      <Tag color={decision.status === 'accepted' ? 'green' : decision.status === 'rejected' ? 'red' : 'default'}>
                        {decision.status || 'pending'}
                      </Tag>
                      <Text type="secondary">{formatPercent(decision.confidence)}</Text>
                    </Space>
                    {decision.source_textbooks?.length ? (
                      <div className="decision-source">
                        {decision.source_textbooks.map((tb) => (
                          <Tag key={tb} color="purple">{tb}</Tag>
                        ))}
                      </div>
                    ) : null}
                    <Paragraph ellipsis={{ rows: 2, expandable: true }} style={{ marginBottom: 0 }}>
                      {decision.reason || '暂无说明'}
                    </Paragraph>
                    <Space size={8}>
                      <Button
                        size="small"
                        onClick={() => handleDecisionStatus(decision.decision_id, 'accept')}
                        loading={!!actionLoading[`accept:${decision.decision_id}`]}
                      >
                        接受
                      </Button>
                      <Button
                        size="small"
                        danger
                        ghost
                        onClick={() => handleDecisionStatus(decision.decision_id, 'reject')}
                        loading={!!actionLoading[`reject:${decision.decision_id}`]}
                      >
                        驳回
                      </Button>
                    </Space>
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
              <Button onClick={handleBuildRAGIndex} icon={<BuildOutlined />} loading={!!actionLoading.ragIndex} block>
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
                loading={!!actionLoading.ragQuery}
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
              <Button type="primary" onClick={handleChat} loading={!!actionLoading.chat}>
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
            <Button onClick={handleLoadReport} loading={!!actionLoading.report} icon={<ReloadOutlined />} block>
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
              <Card className="panel-card markdown-report-card" title="报告内容">
                <ReactMarkdown>{reportMarkdown}</ReactMarkdown>
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
      {busy ? (
        <div className="loading-overlay">
          <Spin size="large" tip={busy} />
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
              左侧管理教材与章节覆盖，中间展示图谱主视图，右侧用于整合、RAG、对话和报告。
              这次补上了章节列表视图、报告阅读层和更细的局部加载反馈。
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
                    <Button block onClick={handleParseAll} loading={!!actionLoading.parseAll}>解析全部</Button>
                  </Col>
                  <Col span={12}>
                    <Button block type="primary" icon={<BuildOutlined />} onClick={handleBuildAllKG} loading={!!actionLoading.buildAllKG}>批量建图</Button>
                  </Col>
                </Row>

                <Divider style={{ margin: '4px 0 0' }} />

                <div className="book-list">
                  {textbooks.map((book, index) => {
                    const statusItem = pipelineStatus?.textbooks?.find((item) => item.book_id === book.id);
                    const tone = BOOK_COLORS[index % BOOK_COLORS.length];
                    return (
                      <div
                        key={book.id}
                        className={`book-row ${selectedBook === book.id ? 'active' : ''}`}
                        style={{ '--tone': tone }}
                        onClick={() => handleShowGraph(book.id)}
                      >
                        <div className="book-row-main">
                          <Text strong>{book.title}</Text>
                          <Text type="secondary">
                            {book.total_pages || statusItem?.parsed?.total_pages || 0} 页 · {book.total_chars ? formatNumber(book.total_chars) : '--'} 字
                          </Text>
                          <div className="book-meta-inline">
                            <Tag color={book.status === 'parsed' ? 'green' : 'blue'}>{book.status}</Tag>
                            <Tag>{statusItem?.knowledge_graph?.chapters_processed || 0}/{statusItem?.knowledge_graph?.chapters_total || 0} 章图谱</Tag>
                          </div>
                        </div>
                        <div className="book-actions">
                          <Space direction="vertical" size={0}>
                            <Button
                              size="small"
                              type="link"
                              loading={!!actionLoading[`build:${book.id}`]}
                              onClick={(event) => {
                                event.stopPropagation();
                                handleBuildKG(book.id);
                              }}
                            >
                              建图
                            </Button>
                            <Button
                              size="small"
                              type="link"
                              danger
                              loading={!!actionLoading[`delete:${book.id}`]}
                              onClick={(event) => {
                                event.stopPropagation();
                                handleDeleteTextbook(book.id);
                              }}
                            >
                              删除
                            </Button>
                          </Space>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {selectedBook !== 'merged' && selectedChapters ? (
                  <Card size="small" className="chapter-card" title={`章节覆盖 · 已建图 ${selectedChapters.processed_chapters}/${selectedChapters.total_chapters}`}>
                    <div className="chapter-progress">
                      <div
                        className="chapter-progress-fill"
                        style={{ width: `${selectedChapters.total_chapters ? (selectedChapters.processed_chapters / selectedChapters.total_chapters) * 100 : 0}%` }}
                      />
                    </div>
                    <div className="chapter-list" style={{ marginTop: 10 }}>
                      {selectedChapters.chapters.map((chapter) => (
                        <div key={chapter.chapter_id} className={`chapter-row ${chapter.is_processed ? 'processed' : ''}`}>
                          <div className="chapter-row-main">
                            <Text strong>{chapter.sequence}. {chapter.title}</Text>
                            <Text type="secondary">第 {chapter.page_start}-{chapter.page_end} 页 · {formatNumber(chapter.char_count)} 字</Text>
                          </div>
                          <Tag color={chapter.is_processed ? 'green' : 'default'}>
                            {chapter.is_processed ? '已建图' : '未建图'}
                          </Tag>
                        </div>
                      ))}
                    </div>
                  </Card>
                ) : null}

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
                <Space wrap size={8}>
                  <Input.Search
                    placeholder="搜索节点..."
                    size="small"
                    allowClear
                    onSearch={(val) => setGraphSearch(val)}
                    onChange={(e) => { if (!e.target.value) setGraphSearch(''); }}
                    className="graph-search"
                  />
                  {selectedBook === 'merged' && textbooks.length > 0 ? (
                    <Select
                      mode="multiple"
                      size="small"
                      placeholder="筛选教材"
                      allowClear
                      maxTagCount={2}
                      maxTagPlaceholder={(omitted) => `+${omitted.length}`}
                      style={{ minWidth: 160 }}
                      options={textbooks.map((b) => ({ label: b.title, value: b.id }))}
                      value={graphBookFilter}
                      onChange={setGraphBookFilter}
                    />
                  ) : null}
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
