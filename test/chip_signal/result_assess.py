import os, time
from collections import defaultdict
from statsmodels.stats.multitest import fdrcorrection
from scipy.stats import combine_pvalues
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, fbeta_score, roc_auc_score, roc_curve, auc, average_precision_score, precision_recall_curve, PrecisionRecallDisplay

class OCR:
    def __init__(self, ocr_id, chr, start, end, pValue, fdr):
        self.ocr_id = ocr_id
        self.chr = chr
        self.start = start
        self.end = end
        self.pValue = pValue
        self.fdr = fdr

    def __str__(self):
        return f"({self.ocr_id},{self.chr},{self.start},{self.end},{self.pValue},{self.fdr})"

def load_k562_mcf7_ocrs():
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    OCR_POS_FILE = os.path.join(ROOT_DIR, 'data', 'CTCF_ChIP_seq', 'chipseq_k562_mcf7_combined_peak.bed')
    # OCR_FDR_FILE = os.path.join(ROOT_DIR, 'data', 'CTCF_ChIP_seq', 'K562_MCF7_edgeR_ChIP_signal_results.csv')
    OCR_FDR_FILE = os.path.join(ROOT_DIR, 'data', 'CTCF_ChIP_seq', 'K562_MCF7_pvalues.csv')
    with open(OCR_POS_FILE, 'r') as f:
        lines = f.readlines()
    with open(OCR_FDR_FILE, 'r') as f:
        lines2 = f.readlines()[1:]
    ocrs_list = list()
    i = 0
    for line, line2 in zip(lines, lines2):
        line = line.strip().split('\t')
        line2 = line2.strip().split(',')
        ocrs_list.append(OCR(i, line[0][3:], int(line[1]), int(line[2]), float(line2[4]), float(line2[5])))
        i += 1
    return ocrs_list

class Anchor:
    def __init__(self, anchor_id, chr, start, end):
        self.anchor_id = anchor_id
        self.chr = chr
        self.start = start
        self.end = end

    def __str__(self):
        return f"({self.anchor_id},{self.chr},{self.start},{self.end})"

class Interaction:
    def __init__(self, anchor1, anchor2, pvalue, fdr):
        self.chr = anchor1.chr
        self.anchor1 = anchor1
        self.anchor2 = anchor2
        self.pvalue = pvalue
        self.fdr = fdr
        self.ocrs = list()

    def __str__(self):
        return f"[{self.chr},{self.anchor1},{self.anchor2},{self.pvalue},{self.fdr}]"

def load_diffloop_result_anchors(anchors_file, interactions_file, fdrs_file):
    """
    Load diffloop result anchors from ROOT_DIR/data/diffloop_results/{cell_line1}_{cell_line2}_diffloop_mydata_results_anchors.csv
    """
    with open(anchors_file, 'r') as f:
        lines = f.readlines()[1:]
    anchors = dict()
    for line in lines:
        line = line.strip().split(',')
        anchors[int(line[0].strip('"'))] = Anchor(int(line[0].strip('"')), line[1].strip('"'), int(line[2]), int(line[3]))

    with open(interactions_file, 'r') as f:
        lines1 = f.readlines()[1:]
    with open(fdrs_file, 'r') as f:
        lines2 = f.readlines()[1:]
    interactions = []
    for line1, line2 in zip(lines1, lines2):
        line1 = line1.strip().split(',')
        line2 = line2.strip().split(',')
        # print(line1)
        interactions.append(Interaction(anchors[int(float(line1[1]))], anchors[int(float(line1[2]))], float(line2[7]), float(line2[8])))
    return interactions


def judge_overlap(gene, interaction):
    # if not in two anchors region
    if gene.end < interaction.anchor1.start or \
        (gene.start > interaction.anchor1.end and gene.end < interaction.anchor2.start) or \
        gene.start > interaction.anchor2.end:
        return False
    return True

def load_diffloop_result():
    time1 = time.time()
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    DIFFLOOP_RESULT_DIR = os.path.join(ROOT_DIR, 'test', 'rna_exp')
    anchors_file = os.path.join(DIFFLOOP_RESULT_DIR, 'K562_MCF7_diffloop_mydata_results_anchors.csv')
    interactions_file = os.path.join(DIFFLOOP_RESULT_DIR, 'K562_MCF7_diffloop_mydata_results_interactions.csv')
    fdrs_file = os.path.join(DIFFLOOP_RESULT_DIR, 'K562_MCF7_diffloop_mydata_results_FDR.csv')

    TEST_DIR = os.path.join(ROOT_DIR, 'test', 'chip_signal')

    # * Load diffloop result interactions
    interactions = load_diffloop_result_anchors(anchors_file, interactions_file, fdrs_file)
    print(interactions[0])
    print(len(interactions)) # 299805
    print(type(interactions[0].chr))

    # * Load ocrs from gff3 and edgeR_rna_file
    ocrs = load_k562_mcf7_ocrs()
    print(ocrs[0])
    print(len(ocrs)) # 115282
    print(type(ocrs[0].chr))
    ocrs_dict = defaultdict(list)
    for ocr in ocrs:
        ocrs_dict[ocr.chr].append(ocr)

    # * Add ocrs to interactions
    i = 0
    for interaction in interactions:
        i += 1
        if i % 1000 == 0:
            print(i)
        for ocr in ocrs_dict[interaction.chr]:
            if judge_overlap(ocr, interaction):
                interaction.ocrs.append(ocr)
    interactions_with_ocrs = [interaction for interaction in interactions if interaction.ocrs]
    print(len(interactions_with_ocrs)) # 237036
    print(interactions_with_ocrs[0])
    # for i in interactions_with_ocrs[0].ocrs:
    #     print(i)
    for i in interactions_with_ocrs:
        i.gene_pvalues = ";".join([str(gene.pValue) for gene in i.ocrs])
        i.gene_fdrs = ";".join([str(gene.fdr) for gene in i.ocrs])

    with open(os.path.join(TEST_DIR, 'diffloop_interactions.csv'), 'w') as f:
        for i in interactions_with_ocrs:
            f.write(f"{i.chr}\t{i.anchor1.start}\t{i.anchor1.end}\t{i.anchor2.start}\t{i.anchor2.end}\t{i.pvalue}\t{i.fdr}\t{i.gene_pvalues}\t{i.gene_fdrs}\n")

    print("Time:", time.time()-time1)

def load_my_result(my_result_file):
    time1 = time.time()
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    TEST_DIR = os.path.join(ROOT_DIR, 'test', 'rna_exp')
    # * Load my result interactions
    with open(os.path.join(TEST_DIR, 'my_dci_result', my_result_file), 'r') as f:
        lines = f.readlines()
    interactions = list()
    for line in lines:
        line = line.strip().split('\t')
        anchor1 = Anchor(0, line[0][3:], int(line[1]), int(line[2]))
        anchor2 = Anchor(0, line[0][3:], int(line[3]), int(line[4]))
        interactions.append(Interaction(anchor1, anchor2, float(line[5]), float(line[6])))
    print(interactions[0])
    print(len(interactions)) # 43710
    print(type(interactions[0].chr))

    # * Load ocrs from gff3 and edgeR_rna_file
    ocrs = load_k562_mcf7_ocrs()
    print(ocrs[0])
    print(len(ocrs)) # 115282
    print(type(ocrs[0].chr))
    ocrs_dict = defaultdict(list)
    for ocr in ocrs:
        ocrs_dict[ocr.chr].append(ocr)

    # * Add ocrs to interactions
    i = 0
    for interaction in interactions:
        i += 1
        if i % 1000 == 0:
            print(i)
        for gene in ocrs_dict[interaction.chr]:
            if judge_overlap(gene, interaction):
                interaction.ocrs.append(gene)
    interactions_with_genes = [interaction for interaction in interactions if interaction.ocrs]
    print(interactions_with_genes[0])
    print(len(interactions_with_genes)) # 31730
    # for i in interactions_with_genes[0].ocrs:
    #     print(i)
    for i in interactions_with_genes:
        i.gene_pvalues = ";".join([str(gene.pValue) for gene in i.ocrs])
        i.gene_fdrs = ";".join([str(gene.fdr) for gene in i.ocrs])

    with open(os.path.join(ROOT_DIR, "test", "chip_signal", 'my_dci_result', 'my_interactions.csv'), 'w') as f:
        for i in interactions_with_genes:
            f.write(f"{i.chr}\t{i.anchor1.start}\t{i.anchor1.end}\t{i.anchor2.start}\t{i.anchor2.end}\t{i.pvalue}\t{i.fdr}\t{i.gene_pvalues}\t{i.gene_fdrs}\n")

    print("Time:", time.time()-time1)


def load_diffloop_result_with_counts_after_myQC():
    time1 = time.time()
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


    RNA_TEST_DIR = os.path.join(ROOT_DIR, 'test', 'rna_exp')
    # * Load my result interactions
    with open(os.path.join(RNA_TEST_DIR, 'my_dci_result', 'my_dci_result_nonorm_kde.csv'), 'r') as f:
        lines = f.readlines()
    with open(os.path.join(RNA_TEST_DIR, 'K562_MCF7_diffloop_mydata_result_with_counts_after_myQC.csv'), 'r') as f:
        lines2 = f.readlines()[1:]
    interactions = list()
    for line, line2 in zip(lines, lines2):
        line = line.strip().split('\t')
        line2 = line2.strip().split(',')
        anchor1 = Anchor(0, line[0][3:], int(line[1]), int(line[2]))
        anchor2 = Anchor(0, line[0][3:], int(line[3]), int(line[4]))
        interactions.append(Interaction(anchor1, anchor2, float(line2[4]), float(line2[5])))
    print(interactions[0])
    print(len(interactions)) # 43710
    print(type(interactions[0].chr))

    # * Load ocrs from gff3 and edgeR_rna_file
    ocrs = load_k562_mcf7_ocrs()
    print(ocrs[0])
    print(len(ocrs)) # 115282
    print(type(ocrs[0].chr))
    ocrs_dict = defaultdict(list)
    for ocr in ocrs:
        ocrs_dict[ocr.chr].append(ocr)

    # * Add ocrs to interactions
    i = 0
    for interaction in interactions:
        i += 1
        if i % 1000 == 0:
            print(i)
        for gene in ocrs_dict[interaction.chr]:
            if judge_overlap(gene, interaction):
                interaction.ocrs.append(gene)
    interactions_with_genes = [interaction for interaction in interactions if interaction.ocrs]
    print(interactions_with_genes[0])
    print(len(interactions_with_genes)) # 31730
    for i in interactions_with_genes[0].ocrs:
        print(i)
    for i in interactions_with_genes:
        i.gene_pvalues = ";".join([str(gene.pValue) for gene in i.ocrs])
        i.gene_fdrs = ";".join([str(gene.fdr) for gene in i.ocrs])

    with open(os.path.join(ROOT_DIR, "test", "chip_signal", 'diffloop_interactions_with_counts_after_myQC.csv'), 'w') as f:
        for i in interactions_with_genes:
            f.write(f"{i.chr}\t{i.anchor1.start}\t{i.anchor1.end}\t{i.anchor2.start}\t{i.anchor2.end}\t{i.pvalue}\t{i.fdr}\t{i.gene_pvalues}\t{i.gene_fdrs}\n")

    print("Time:", time.time()-time1)



def result_metrics(filename, fdr_threshold=0.05):
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEST_DIR = os.path.join(ROOT_DIR, 'test', 'chip_signal')
    print(filename)
    with open(os.path.join(TEST_DIR, filename), 'r') as f:
        lines = f.readlines()
    pred_score = list()
    labels = list()
    merged_p_values = list()
    for i in lines:
        i = i.strip().split('\t')
        pred_score.append(float(i[6]))
        # fdrs = i[7].split(';')
        # has_diff = False
        # for fdr in fdrs:
        #     if float(fdr) < fdr_threshold:
        #         has_diff = True
        #         break
        # labels.append(int(has_diff))
        pvalues = [float(j) for j in i[7].split(';')]
        _, merged_p_value = combine_pvalues(pvalues, method='mudholkar_george')
        merged_p_values.append(merged_p_value)
    _, fdrs_merged = fdrcorrection(merged_p_values, alpha=0.05, method='indep', is_sorted=False)
    pred_score = np.array(pred_score)
    labels = np.array(fdrs_merged<fdr_threshold, dtype=int)

    print(f"sum(pred_score < {fdr_threshold}): {sum(pred_score < fdr_threshold)}")
    print(f"positive labels number:negative: {sum(labels)}:{len(labels)-sum(labels)}")
    # make prediction=1 when pred_score < fdr_threshold
    predictions = np.zeros(pred_score.shape)
    predictions[pred_score < fdr_threshold] = 1
    # compute metrics
    acc = accuracy_score(labels, predictions)
    precision = precision_score(labels, predictions)
    recall = recall_score(labels, predictions)
    f1 = f1_score(labels, predictions)
    fbeta = fbeta_score(y_true=labels, y_pred=predictions, beta=2)

    auroc = roc_auc_score(labels, 1-pred_score)
    fpr, tpr, thresholds = roc_curve(labels, 1-pred_score)
    auroc_by_auc = auc(fpr, tpr)

    auprc = average_precision_score(labels, 1-pred_score)
    precision_point, recall_point, thresholds = precision_recall_curve(labels, 1-pred_score, pos_label=1)
    # precision_point[(recall_point==0)] = 1.0
    auprc_by_auc = auc(recall_point, precision_point)
    # print(f"accuracy: {acc}, precision: {precision}, recall: {recall}, f1: {f1}, fbeta: {fbeta}, auroc: {auroc}, auroc_by_auc: {auroc_by_auc}, auprc: {auprc}, auprc_by_auc: {auprc_by_auc}")
    print(f"accuracy: {acc}, precision: {precision}, recall: {recall}, f1: {f1}, fbeta: {fbeta}, auroc: {auroc}, auprc: {auprc}")
    # import matplotlib.pyplot as plt
    # ax = plt.gca()
    # pr_display1 = PrecisionRecallDisplay(precision=precision_point, recall=recall_point)
    # pr_display1.plot(ax=ax, name="mine", color="red")
    # plt.show()
    return fpr, tpr, auroc_by_auc, precision_point, recall_point, auprc_by_auc


if __name__ == "__main__":
    # diffloop result combine with gene expression
    # load_diffloop_result()
    # diffloop result with counts after my QC combine with gene expression
    # load_diffloop_result_with_counts_after_myQC()
    # my result combine with gene expression
    load_my_result("my_dci_result_ssrdnorm_neighbor.csv")

    # result_metrics("diffloop_interactions.csv", 0.05)
    # result_metrics("diffloop_interactions_with_counts_after_myQC.csv", 0.05)
    result_metrics(os.path.join("my_dci_result", "my_interactions.csv"), 0.05)
