#include <algorithm>
#include <iterator>
#include "pybind11_opencv/cvbind.hpp"
#include <opencv2/opencv.hpp>

namespace py = pybind11;


// The following code is copied from opencv/modules/imgproc/src/hough.cpp

namespace cv {


struct LinePolar
{
    float rho;
    float angle;
};


struct hough_cmp_gt
{
    hough_cmp_gt(const int* _aux) : aux(_aux) {}
    inline bool operator()(int l1, int l2) const
    {
        return aux[l1] > aux[l2] || (aux[l1] == aux[l2] && l1 < l2);
    }
    const int* aux;
};


static inline int
computeNumangle( double min_theta, double max_theta, double theta_step )
{
    int numangle = cvFloor((max_theta - min_theta) / theta_step) + 1;
    // If the distance between the first angle and the last angle is
    // approximately equal to pi, then the last angle will be removed
    // in order to prevent a line to be detected twice.
    if ( numangle > 1 && fabs(CV_PI - (numangle-1)*theta_step) < theta_step/2 )
        --numangle;
    return numangle;
}


static void
createTrigTable( int numangle, double min_theta, double theta_step,
                 float irho, float *tabSin, float *tabCos )
{
    float ang = static_cast<float>(min_theta);
    for(int n = 0; n < numangle; ang += (float)theta_step, n++ )
    {
        tabSin[n] = (float)(sin((double)ang) * irho);
        tabCos[n] = (float)(cos((double)ang) * irho);
    }
}


static void
findLocalMaximums( int numrho, int numangle, int threshold,
                   const int *accum, std::vector<int>& sort_buf )
{
    for(int r = 0; r < numrho; r++ )
        for(int n = 0; n < numangle; n++ )
        {
            int base = (n+1) * (numrho+2) + r+1;
            if( accum[base] > threshold &&
                accum[base] > accum[base - 1] && accum[base] >= accum[base + 1] &&
                accum[base] > accum[base - numrho - 2] && accum[base] >= accum[base + numrho + 2] )
                sort_buf.push_back(base);
        }
}


static void
HoughLinesStandard( InputArray src, OutputArray lines, int type,
                    float rho, float theta,
                    int threshold, int linesMax,
                    double min_theta, double max_theta, bool use_edgeval = false )
{
    CV_CheckType(type, type == CV_32FC2 || type == CV_32FC3, "Internal error");

    Mat img = src.getMat();

    int i, j;
    float irho = 1 / rho;

    CV_Assert( img.type() == CV_8UC1 );
    CV_Assert( linesMax > 0 );

    const uchar* image = img.ptr();
    int step = (int)img.step;
    int width = img.cols;
    int height = img.rows;

    int max_rho = width + height;
    int min_rho = -max_rho;

    CV_CheckGE(max_theta, min_theta, "max_theta must be greater than min_theta");

    int numangle = computeNumangle(min_theta, max_theta, theta);
    int numrho = cvRound(((max_rho - min_rho) + 1) / rho);

    Mat _accum = Mat::zeros( (numangle+2), (numrho+2), CV_32SC1 );
    std::vector<int> _sort_buf;
    AutoBuffer<float> _tabSin(numangle);
    AutoBuffer<float> _tabCos(numangle);
    int *accum = _accum.ptr<int>();
    float *tabSin = _tabSin.data(), *tabCos = _tabCos.data();

    // create sin and cos table
    createTrigTable( numangle, min_theta, theta,
                     irho, tabSin, tabCos);

    // stage 1. fill accumulator
    if (use_edgeval) {
        for( i = 0; i < height; i++ )
            for( j = 0; j < width; j++ )
            {
                if( image[i * step + j] != 0 )
                    for(int n = 0; n < numangle; n++ )
                    {
                        int r = cvRound( j * tabCos[n] + i * tabSin[n] );
                        r += (numrho - 1) / 2;
                        accum[(n + 1) * (numrho + 2) + r + 1] += image[i * step + j];
                     }
             }
    } else {
        for( i = 0; i < height; i++ )
            for( j = 0; j < width; j++ )
            {
                if( image[i * step + j] != 0 )
                    for(int n = 0; n < numangle; n++ )
                    {
                        int r = cvRound( j * tabCos[n] + i * tabSin[n] );
                        r += (numrho - 1) / 2;
                        accum[(n + 1) * (numrho + 2) + r + 1]++;
                    }
            }
     }

    // stage 2. find local maximums
    findLocalMaximums( numrho, numangle, threshold, accum, _sort_buf );

    // stage 3. sort the detected lines by accumulator value
    std::sort(_sort_buf.begin(), _sort_buf.end(), hough_cmp_gt(accum));

    // stage 4. store the first min(total,linesMax) lines to the output buffer
    linesMax = std::min(linesMax, (int)_sort_buf.size());
    double scale = 1./(numrho+2);

    lines.create(linesMax, 1, type);
    Mat _lines = lines.getMat();
    for( i = 0; i < linesMax; i++ )
    {
        LinePolar line;
        int idx = _sort_buf[i];
        int n = cvFloor(idx*scale) - 1;
        int r = idx - (n+1)*(numrho+2) - 1;
        line.rho = (r - (numrho - 1)*0.5f) * rho;
        line.angle = static_cast<float>(min_theta) + n * theta;
        if (type == CV_32FC2)
        {
            _lines.at<Vec2f>(i) = Vec2f(line.rho, line.angle);
        }
        else
        {
            CV_DbgAssert(type == CV_32FC3);
            _lines.at<Vec3f>(i) = Vec3f(line.rho, line.angle, (float)accum[idx]);
        }
    }
}

}  // namespace cv


cv::Mat hough_lines_with_votes(
    const cv::Mat& image, double rho, double theta, int threshold,
    double min_theta, double max_theta, bool use_edgeval
) {
    std::vector<cv::Vec3f> vec_lines {};
    cv::HoughLinesStandard(
        image, vec_lines, CV_32FC3, (float)rho, (float)theta, threshold,
       	INT_MAX, min_theta, max_theta, use_edgeval
    );
    cv::Mat lines(vec_lines);
    return lines;
}


PYBIND11_MODULE(hough, m) {
    // Initialize the cv::Mat to numpy.ndarray converter
    m.doc() = "Custom OpenCV Hough Lines binding that returns vote counts.";

    m.def("hough_lines_with_votes", &hough_lines_with_votes,
          "Finds lines in a binary image using the Hough transform and returns votes.",
      py::arg("image"),
      py::arg("rho"),
      py::arg("theta"),
      py::arg("threshold"),
	  py::arg("min_theta"),
	  py::arg("max_theta"),
	  py::arg("use_edgeval")
    );
}

