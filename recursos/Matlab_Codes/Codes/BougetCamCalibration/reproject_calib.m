%%%%%%%%%%%%%%%%%%%% REPROJECT ON THE IMAGES %%%%%%%%%%%%%%%%%%%%%%%%

if ~exist('n_ima')|~exist('fc'),
   fprintf(1,'No calibration data available.\n');
   return;
end;

if ~exist('no_image'),
   no_image = 0;
end;

if ~exist('nx')&~exist('ny'),
   fprintf(1,'WARNING: No image size (nx,ny) available. Setting nx=640 and ny=480\n');
   nx = 640;
   ny = 480;
end;


% check_active_images;


% Color code for each image:

colors = 'brgkcm';

% Reproject the patterns on the images, and compute the pixel errors:

% Reload the images if necessary
if n_ima ~= 0,
if ~exist(['omc_' num2str(ind_active(1)) ]),
   fprintf(1,'Need to calibrate before showing image reprojection. Maybe need to load Calib_Results.mat file.\n');
   return;
end;
end;

% if n_ima ~= 0,
% if ~no_image,
% 	if ~exist(['I_' num2str(ind_active(1)) ]'),
% 	   n_ima_save = n_ima;
% 	   active_images_save = active_images;
% 	   ima_read_calib;
% 	   n_ima = n_ima_save;
% 	   active_images = active_images_save;
% 	   check_active_images;
%    	if no_image_file,
% 	   fprintf(1,'WARNING: Do not show the original images\n'); %return;
%    	end;
%    end;
% else
%    no_image_file = 1;
% end;
% end;


if ~exist('dont_ask'),
   dont_ask = 0;
end;


% if (~dont_ask)&(length(ind_active)>1),
%    ima_numbers = input('Number(s) of image(s) to show ([] = all images) = ');
% else
%    ima_numbers = [];
% end;


% if isempty(ima_numbers),
%    ima_proc = 1:n_ima;
% else
%    ima_proc = ima_numbers;
% end;


g=figure;
for kk = 1:n_ima,
   if exist(['y_' num2str(kk)]),
   if active_images(kk) & eval(['~isnan(y_' num2str(kk) '(1,1))']),
	   eval(['plot(ex_' num2str(kk) '(1,:),ex_' num2str(kk) '(2,:),''' colors(rem(kk-1,6)+1) '+'');']);
      hold on;
   end;
   end;
end;
hold off;
axis('equal');
title('Reprojection error (in pixel)');
xlabel('x');
ylabel('y');
drawnow;
if n_ima==0,
    text(.5,.5,'No image data available','fontsize',24,'horizontalalignment' ,'center');
end;


set(g,'color',[1 1 1]);
set(g,'Name','error','NumberTitle','off');


if n_ima ~= 0,
err_std = std(ex')';
fprintf(1,'Pixel error:      err = [%3.5f   %3.5f] (all active images)\n\n',err_std); 
end;
